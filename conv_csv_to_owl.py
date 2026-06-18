import pandas as pd
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, SKOS
import re



# How to run
# Delete top couple of rows until the first row is "procedure" or the first term
# Clean up other rows such as the ones on the bottom
# Save as csv and rename to ontology.csv
# Run this command python conv_csv_to_owl.py
# nuclex.owl will be created which can be uploaded to protege
# =========================
# CONFIG
# =========================

CSV_FILE = "ontology.csv"
OUTPUT_FILE = "nuclex.owl"

BASE_IRI = "http://nuclex.org/ontology/"

# =========================
# NAMESPACES
# =========================

g = Graph()

NUCLEX = Namespace(BASE_IRI)
OIO = Namespace("http://www.geneontology.org/formats/oboInOwl#")
IAO = Namespace("http://purl.obolibrary.org/obo/IAO_")

g.bind("owl", OWL)
g.bind("rdfs", RDFS)
g.bind("skos", SKOS)
g.bind("oio", OIO)
g.bind("iao", IAO)

annotation_columns = [
    "nuclex_nid",
    "parent_OBO",
    "obo_id",
    "obo_axiom",
    "radlex_purl",
    "radlex_axiom",
    "playbook_rpid",
    "umls_cui",
    "umls_axiom",
    "nci_thesaurus_code",
    "nci_thesaurus_axiom",
    "snomedct_code",
    "snomedct_axiom",
    "ibsi_code",
    "ibsi_axiom",
    "dicom_code",
    "Other",
    "Other_axiom",
    "Measurement?",
    "Assignment ID",
    "Approver/Endorser ID",
    "Comments",
    "Synonyms",
    "Definitions"
]

annotation_properties = {}

for col in annotation_columns:

    safe_name = re.sub(
        r"[^A-Za-z0-9_]",
        "_",
        col
    )

    prop_uri = URIRef(
        BASE_IRI + safe_name
    )

    annotation_properties[col] = prop_uri

    g.add(
        (
            prop_uri,
            RDF.type,
            OWL.AnnotationProperty
        )
    )

    g.add(
        (
            prop_uri,
            RDFS.label,
            Literal(col)
        )
    )

# =========================
# HIERARCHY COLUMNS
# =========================

hierarchy_cols = [
    "Class",
    "Subclass2",
    "Subclass3",
    "Subclass4",
    "Subclass5",
    "Subclass6",
    "Subclass7",
    "Subclass8",
]

# =========================
# HELPERS
# =========================

def clean_id(nuclex_id):
    return re.sub(r"[^A-Za-z0-9_]", "_", str(nuclex_id))

def create_class(uri, label):
    if (uri, RDF.type, OWL.Class) not in g:
        g.add((uri, RDF.type, OWL.Class))
        g.add((uri, RDFS.label, Literal(label)))

def add_literal_annotation(subject, predicate, value):
    if pd.notna(value) and str(value).strip():
        g.add((subject, predicate, Literal(str(value).strip())))


# =========================
# READ CSV
# =========================

df = pd.read_csv(CSV_FILE)

# Keeps track of the hierarchy path
current_path = [None] * len(hierarchy_cols)

# Maps labels to URIs
label_to_uri = {}

# =========================
# BUILD ONTOLOGY
# =========================

for _, row in df.iterrows():

    # Update hierarchy state
    for level, col in enumerate(hierarchy_cols):

        value = row.get(col)

        if pd.notna(value) and str(value).strip():

            current_path[level] = str(value).strip()

            # Clear deeper levels
            for deeper in range(level + 1, len(hierarchy_cols)):
                current_path[deeper] = None

            break

    path_terms = [x for x in current_path if x]

    if not path_terms:
        continue

    # Determine leaf term
    leaf_label = path_terms[-1]

    nuclex_id = row.get("nuclex_nid")

    if pd.isna(nuclex_id):
        continue

    leaf_uri = URIRef(
        BASE_IRI + clean_id(nuclex_id)
    )

    label_to_uri[leaf_label] = leaf_uri

    create_class(leaf_uri, leaf_label)

    add_literal_annotation(
        leaf_uri,
        OIO.id,
        nuclex_id
    )

    # Synonyms
    if "Synonyms" in row.index:

        syns = row["Synonyms"]

        if pd.notna(syns):

            for syn in str(syns).split(","):

                syn = syn.strip()

                if syn:
                    g.add(
                        (
                            leaf_uri,
                            SKOS.altLabel,
                            Literal(syn)
                        )
                    )

    # Definition
    if "Definitions" in row.index:
        add_literal_annotation(
            leaf_uri,
            IAO["0000115"],
            row["Definitions"]
        )

    # Comment
    if "Comments" in row.index:
        add_literal_annotation(
            leaf_uri,
            RDFS.comment,
            row["Comments"]
        )

    for col, prop_uri in annotation_properties.items():

        if col not in row.index:
            continue

        value = row[col]

        if pd.isna(value):
            continue

        value = str(value).strip()

        if not value:
            continue

        g.add(
            (
                leaf_uri,
                prop_uri,
                Literal(value)
            )
        )

    # =====================
    # CREATE ANCESTORS
    # =====================

    parent_uri = None

    for i, term in enumerate(path_terms):

        if term == leaf_label:
            current_uri = leaf_uri

        else:

            if term not in label_to_uri:

                generated_uri = URIRef(
                    BASE_IRI +
                    re.sub(r"[^A-Za-z0-9_]", "_", term)
                )

                label_to_uri[term] = generated_uri

                create_class(
                    generated_uri,
                    term
                )

            current_uri = label_to_uri[term]

        if parent_uri is not None:

            g.add(
                (
                    current_uri,
                    RDFS.subClassOf,
                    parent_uri
                )
            )

        parent_uri = current_uri

# =========================
# SAVE
# =========================

g.serialize(
    destination=OUTPUT_FILE,
    format="pretty-xml"
)

print()
print("Finished.")
print(f"Saved ontology to {OUTPUT_FILE}")
print(f"Total classes: {len(label_to_uri)}")