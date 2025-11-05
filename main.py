import os
from typing import List, Optional

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import Patient, Researcher, ForumQuestion, ForumReply, Favorite

app = FastAPI(title="CuraLink API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "CuraLink Backend is running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, "name") else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"

    return response


# -----------------------------
# Onboarding persistence
# -----------------------------

@app.post("/api/patient")
def create_patient_profile(payload: Patient):
    new_id = create_document("patient", payload)
    return {"id": new_id}


@app.post("/api/researcher")
def create_researcher_profile(payload: Researcher):
    new_id = create_document("researcher", payload)
    return {"id": new_id}


# -----------------------------
# Forums
# -----------------------------

@app.post("/api/forums/questions")
def create_forum_question(payload: ForumQuestion):
    if payload.author_role != "patient":
        raise HTTPException(status_code=403, detail="Only patients can create questions")
    new_id = create_document("forumquestion", payload)
    return {"id": new_id}


@app.get("/api/forums/questions")
def list_forum_questions(tag: Optional[str] = None, category: Optional[str] = None, limit: int = 50):
    flt = {}
    if tag:
        flt["tags"] = {"$in": [tag]}
    if category:
        flt["category"] = category
    items = get_documents("forumquestion", flt, limit)
    # Convert ObjectId to string
    for it in items:
        it["_id"] = str(it.get("_id"))
    return {"items": items}


@app.post("/api/forums/replies")
def create_forum_reply(payload: ForumReply):
    if payload.author_role != "researcher":
        raise HTTPException(status_code=403, detail="Only researchers can reply")
    new_id = create_document("forumreply", payload)
    return {"id": new_id}


# -----------------------------
# Favorites
# -----------------------------

@app.post("/api/favorites")
def add_favorite(payload: Favorite):
    new_id = create_document("favorite", payload)
    return {"id": new_id}


@app.get("/api/favorites")
def list_favorites(user_id: Optional[str] = None, user_role: Optional[str] = None, limit: int = 100):
    flt = {}
    if user_id:
        flt["user_id"] = user_id
    if user_role:
        flt["user_role"] = user_role
    items = get_documents("favorite", flt, limit)
    for it in items:
        it["_id"] = str(it.get("_id"))
    return {"items": items}


# -----------------------------
# External Integrations
# -----------------------------

PUBMED_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


@app.get("/api/pubmed/search")
def pubmed_search(query: str = Query(..., min_length=2), max_results: int = 20):
    try:
        # Step 1: search for IDs
        esearch = requests.get(
            f"{PUBMED_EUTILS}/esearch.fcgi",
            params={"db": "pubmed", "term": query, "retmode": "json", "retmax": max_results},
            timeout=10,
        )
        esearch.raise_for_status()
        data = esearch.json()
        id_list = data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return {"items": []}
        # Step 2: fetch summaries
        esummary = requests.get(
            f"{PUBMED_EUTILS}/esummary.fcgi",
            params={"db": "pubmed", "id": ",".join(id_list), "retmode": "json"},
            timeout=10,
        )
        esummary.raise_for_status()
        summ = esummary.json().get("result", {})
        items = []
        for pid in id_list:
            r = summ.get(pid)
            if not r:
                continue
            title = r.get("title")
            journal = r.get("fulljournalname")
            pubdate = r.get("pubdate", "")
            year = None
            try:
                year = int(pubdate[:4]) if pubdate[:4].isdigit() else None
            except Exception:
                year = None
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pid}/"
            items.append({
                "id": pid,
                "title": title,
                "journal": journal,
                "year": year,
                "url": url,
            })
        return {"items": items}
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"PubMed error: {str(e)}")


@app.get("/api/clinical-trials/search")
def clinical_trials_search(
    expr: str = Query(..., description="Query expression, e.g., condition or keywords"),
    min_rank: int = 1,
    max_rank: int = 20,
):
    """Search ClinicalTrials.gov using Study Fields API for broad compatibility."""
    try:
        url = "https://clinicaltrials.gov/api/query/study_fields"
        params = {
            "expr": expr,
            "fields": "NCTId,Condition,BriefTitle,LocationCountry,LocationCity,OverallStatus,StartDate,Phase",
            "min_rnk": min_rank,
            "max_rnk": max_rank,
            "fmt": "json",
        }
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        j = r.json()
        studies = j.get("StudyFieldsResponse", {}).get("StudyFields", [])
        items = []
        for s in studies:
            nct = s.get("NCTId", [None])[0]
            title = s.get("BriefTitle", [""])[0]
            status = s.get("OverallStatus", [None])[0]
            conditions = s.get("Condition", [])
            loc_countries = s.get("LocationCountry", [])
            loc_cities = s.get("LocationCity", [])
            locations = [
                ", ".join(filter(None, [city, country]))
                for city, country in zip(loc_cities + [None] * max(len(loc_countries) - len(loc_cities), 0), loc_countries)
            ] or loc_countries
            items.append(
                {
                    "nct_id": nct,
                    "title": title,
                    "status": status,
                    "conditions": conditions,
                    "locations": locations,
                    "url": f"https://clinicaltrials.gov/study/{nct}" if nct else None,
                }
            )
        return {"items": items}
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"ClinicalTrials.gov error: {str(e)}")


@app.get("/api/orcid/person")
def orcid_person(orcid: str = Query(..., pattern=r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")):
    headers = {"Accept": "application/json"}
    url = f"https://pub.orcid.org/v3.0/{orcid}/person"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        # Minimal shape
        name = data.get("name", {})
        result = {
            "orcid": orcid,
            "given_names": name.get("given-names", {}).get("value"),
            "family_name": name.get("family-name", {}).get("value"),
            "other_names": [n.get("content") for n in data.get("other-names", {}).get("other-name", [])],
            "keywords": [k.get("content") for k in data.get("keywords", {}).get("keyword", [])],
        }
        return result
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"ORCID error: {str(e)}")


class RGPublicationsRequest(BaseModel):
    profile_url: Optional[str] = None
    orcid: Optional[str] = None


@app.post("/api/researchgate/publications")
def researchgate_publications(body: RGPublicationsRequest):
    """
    ResearchGate has no official public API. This endpoint returns a mock set of
    publications inferred from ORCID (if provided) or a deterministic sample for demos.
    """
    seed = (body.orcid or body.profile_url or "demo").strip()
    # Deterministic sample results for stable demos
    base = [
        {
            "title": "Translational Oncology: Bridging Bench to Bedside",
            "journal": "Nature Medicine",
            "year": 2022,
            "url": "https://www.nature.com/",
        },
        {
            "title": "Real-world Evidence in Clinical Trials",
            "journal": "The Lancet",
            "year": 2021,
            "url": "https://www.thelancet.com/",
        },
        {
            "title": "Machine Learning for Precision Medicine",
            "journal": "Science",
            "year": 2020,
            "url": "https://www.science.org/",
        },
    ]
    # Pseudo-random repeatable filtering by seed
    modifier = sum(ord(c) for c in seed) % len(base)
    items = base[modifier:] + base[:modifier]
    return {"items": items}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
