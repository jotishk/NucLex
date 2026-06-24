# How to run
# Delete top couple of rows until the first row is "procedure" or the first term
# Clean up other rows such as the ones on the bottom
# Save as csv and rename to ontology.csv
# Run this command python conv_csv_to_owl.py
# nuclex.owl will be created which can be uploaded to protege
# You can add and remove columns by changing the annotation columns list in this script
# Change in project settings of web_protege to rdf:label to preferred_name
# How to fix preferred name issue - go to project settings and just change new entity language seetings
import pandas as pd
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL
import re

# =========================
# CONFIG
# =========================

CSV_FILE = "ontology.csv"
OUTPUT_FILE = "nuclex.owl"
BASE_IRI = "http://nuclex.org/ontology/"

# =========================
# GRAPH + NAMESPACES
# =========================

g = Graph()

NUCLEX = Namespace(BASE_IRI)
OIO = Namespace("http://www.geneontology.org/formats/oboInOwl#")

g.bind("owl", OWL)
g.bind("rdfs", RDFS)
g.bind("oio", OIO)
g.bind("nuclex", NUCLEX)

# =========================
# CUSTOM PROPERTIES
# =========================

preferred_name_prop = URIRef(BASE_IRI + "preferred_name")
definition_prop = URIRef(BASE_IRI + "definition")
synonym_prop = URIRef(BASE_IRI + "synonym")

for prop, label in [
    (preferred_name_prop, "preferred_name"),
    (definition_prop, "definition"),
    (synonym_prop, "synonym")
]:
    g.add((prop, RDF.type, OWL.AnnotationProperty))
    g.add((prop, RDFS.label, Literal(label)))

# =========================
# ANNOTATION COLUMNS
# =========================

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
]

annotation_properties = {}

for col in annotation_columns:
    safe_name = re.sub(r"[^A-Za-z0-9_]", "_", col)
    prop_uri = URIRef(BASE_IRI + safe_name)

    annotation_properties[col] = prop_uri

    g.add((prop_uri, RDF.type, OWL.AnnotationProperty))
    g.add((prop_uri, RDFS.label, Literal(col)))

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

def clean_id(value):
    return re.sub(r"[^A-Za-z0-9_]", "_", str(value))

def create_class(uri, preferred_name):
    if (uri, RDF.type, OWL.Class) not in g:
        g.add((uri, RDF.type, OWL.Class))

        # preferred name instead of rdfs:label
        g.add((uri, RDFS.label, Literal(preferred_name)))
        g.add((uri, preferred_name_prop, Literal(preferred_name)))

def add_literal(subject, predicate, value):
    if pd.notna(value) and str(value).strip():
        g.add((subject, predicate, Literal(str(value).strip())))

# =========================
# READ CSV
# =========================

df = pd.read_csv(CSV_FILE)
df.columns = df.columns.str.strip()

current_path = [None] * len(hierarchy_cols)
label_to_uri = {}

# =========================
# BUILD ONTOLOGY
# =========================

for _, row in df.iterrows():

    # ---------------------
    # UPDATE HIERARCHY
    # ---------------------

    for level, col in enumerate(hierarchy_cols):

        value = row.get(col)

        if pd.notna(value) and str(value).strip():
            current_path[level] = str(value).strip()

            for deeper in range(level + 1, len(hierarchy_cols)):
                current_path[deeper] = None
            break

    path_terms = [x for x in current_path if x]
    if not path_terms:
        continue

    leaf_name = path_terms[-1]

    nuclex_id = row.get("nuclex_nid")
    if pd.isna(nuclex_id):
        continue

    leaf_uri = URIRef(BASE_IRI + clean_id(nuclex_id))
    label_to_uri[leaf_name] = leaf_uri

    create_class(leaf_uri, leaf_name)

    # ---------------------
    # NUCLEX ID
    # ---------------------

    add_literal(leaf_uri, OIO.id, nuclex_id)

    # ---------------------
    # DEFINITIONS
    # ---------------------

    if "Definitions" in row.index:
        add_literal(leaf_uri, definition_prop, row["Definitions"])

    # ---------------------
    # COMMENTS
    # ---------------------

    if "Comments" in row.index:
        add_literal(leaf_uri, RDFS.comment, row["Comments"])

    # ---------------------
    # SYNONYMS
    # ---------------------

    if "Synonyms" in row.index:
        syns = row["Synonyms"]

        if pd.notna(syns):
            for syn in str(syns).split(","):
                syn = syn.strip()
                if syn:
                    g.add((leaf_uri, synonym_prop, Literal(syn)))

    # ---------------------
    # OTHER ANNOTATIONS
    # ---------------------

    for col, prop_uri in annotation_properties.items():

        if col not in row.index:
            continue

        value = row[col]
        if pd.isna(value):
            continue

        value = str(value).strip()
        if value:
            g.add((leaf_uri, prop_uri, Literal(value)))

    # ---------------------
    # CREATE HIERARCHY
    # ---------------------

    parent_uri = None

    for term in path_terms:

        if term == leaf_name:
            current_uri = leaf_uri

        else:
            if term not in label_to_uri:
                gen_uri = URIRef(
                    BASE_IRI + re.sub(r"[^A-Za-z0-9_]", "_", term)
                )
                label_to_uri[term] = gen_uri
                create_class(gen_uri, term)

            current_uri = label_to_uri[term]

        if parent_uri is not None:
            g.add((current_uri, RDFS.subClassOf, parent_uri))

        parent_uri = current_uri

# =========================
# SAVE
# =========================

g.serialize(destination=OUTPUT_FILE, format="pretty-xml")

print("\nFinished.")
print(f"Saved ontology to {OUTPUT_FILE}")
print(f"Total classes: {len(label_to_uri)}")