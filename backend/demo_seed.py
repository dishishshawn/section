from database import SessionLocal, engine, Base
from models import Project, Tract, Party, Instrument, Interest, Obligation
from datetime import datetime, timedelta


def seed_demo_project():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Check if demo already exists
    existing = db.query(Project).filter(Project.name == "Garfield County 640 - STACK Area").first()
    if existing:
        print("Demo project already exists. Skipping seed.")
        return

    # Create project
    project = Project(
        name="Garfield County 640 - STACK Area", jurisdiction="Oklahoma", owner_org="Compass Operating LLC"
    )
    db.add(project)
    db.flush()
    project_id = project.id

    # Create tract
    tract = Tract(
        project_id=project_id,
        legal_description="All of Section 1, Township 12N, Range 7W, Garfield County, Oklahoma",
        gross_acres=640.0,
    )
    db.add(tract)
    db.flush()
    tract_id = tract.id

    # Create parties
    parties_data = [
        ("Compass Operating LLC", "entity"),
        ("John Smith Estate", "estate"),
        ("Unknown Heir #1", "individual"),
        ("Unknown Heir #2", "individual"),
        ("XYZ Energy LLC", "entity"),
    ]

    parties = {}
    for name, ptype in parties_data:
        p = Party(project_id=project_id, name=name, type=ptype)
        db.add(p)
        db.flush()
        parties[name] = p

    # Create instruments (deeds)
    instr1 = Instrument(
        project_id=project_id,
        type="warranty_deed",
        recorded_at=datetime(2020, 3, 15),
        extracted_data={
            "grantor": "John Smith Estate",
            "grantee": "Compass Operating LLC",
            "legal_description": "All of Section 1",
            "interest": "1/2 mineral interest",
        },
    )
    db.add(instr1)
    db.flush()

    instr2 = Instrument(
        project_id=project_id,
        type="assignment",
        recorded_at=datetime(2021, 6, 1),
        extracted_data={
            "grantor": "Compass Operating LLC",
            "grantee": "Unknown Assignee",
            "interest": "1/4 mineral interest (flagged: incomplete chain)",
        },
    )
    db.add(instr2)
    db.flush()

    instr3 = Instrument(
        project_id=project_id,
        type="lease",
        recorded_at=datetime(2019, 1, 10),
        extracted_data={
            "lessor": "John Smith Estate",
            "lessee": "XYZ Energy LLC",
            "primary_term": "3 years",
            "royalty": "1/8",
            "bonus": 500,
            "pugh_clause": "Yes",
            "depth_limit": "Below 10,000 feet",
        },
    )
    db.add(instr3)
    db.flush()

    # Create interests
    interest1 = Interest(
        tract_id=tract_id,
        party_id=parties["Compass Operating LLC"].id,
        fraction_numerator=1,
        fraction_denominator=2,
        mineral_estate="Surface & Minerals",
        burdens={"royalties": ["1/8 to XYZ Energy"]},
    )
    db.add(interest1)

    interest2 = Interest(
        tract_id=tract_id,
        party_id=parties["John Smith Estate"].id,
        fraction_numerator=1,
        fraction_denominator=4,
        mineral_estate="Minerals Only (ORRI 1/8)",
        burdens={"orri": "1/8 ORRI held by Smith Estate"},
    )
    db.add(interest2)

    interest3 = Interest(
        tract_id=tract_id,
        party_id=parties["Unknown Heir #1"].id,
        fraction_numerator=1,
        fraction_denominator=8,
        mineral_estate="Minerals Only",
        burdens={"restriction": "Title defect - verify heirship"},
    )
    db.add(interest3)

    interest4 = Interest(
        tract_id=tract_id,
        party_id=parties["Unknown Heir #2"].id,
        fraction_numerator=1,
        fraction_denominator=8,
        mineral_estate="Minerals Only",
        burdens={"restriction": "Title defect - verify heirship"},
    )
    db.add(interest4)

    # Create obligations
    now = datetime.now()

    obl1 = Obligation(
        project_id=project_id,
        instrument_id=instr3.id,
        type="primary_term_expiration",
        due_date=now + timedelta(days=90),
        params={"description": "Primary lease term expires"},
    )
    db.add(obl1)

    obl2 = Obligation(
        project_id=project_id,
        instrument_id=instr3.id,
        type="continuous_drilling",
        due_date=now + timedelta(days=45),
        params={"description": "Must drill or plug within 90 days"},
    )
    db.add(obl2)

    obl3 = Obligation(
        project_id=project_id,
        instrument_id=instr3.id,
        type="rental_payment",
        due_date=now + timedelta(days=15),
        params={"amount": 500, "description": "Delay rental due"},
    )
    db.add(obl3)

    db.commit()
    print(f"[SUCCESS] Demo project created: {project.name}")
    print(f"  - Project ID: {project_id}")
    print(f"  - Tract: {tract.legal_description}")
    print(f"  - Parties: {len(parties)}")
    print("  - Interests: 4")
    print("  - Obligations: 3")


if __name__ == "__main__":
    seed_demo_project()
