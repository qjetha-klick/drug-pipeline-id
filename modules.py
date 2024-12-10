import os
import io
import json
import psycopg2

from contextlib import contextmanager

# set up Postgres
DB_PARAMS = {
    "host": os.environ['postgres_host'],
    "dbname": 'drugdb',
    "user": "postgres",
    "password": os.environ['postgres_pwd'],
    "port": '5432'
}

@contextmanager
def get_db_connection():
    conn = psycopg2.connect(**DB_PARAMS)
    conn.autocommit = True
    try:
        yield conn
    finally:
        conn.close()

import json

def get_mesh_conditions():
    query = '''
        SELECT condition_mesh_term 
        FROM ct_mesh_conditions 
        GROUP BY condition_mesh_term
    '''
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Execute the parameterized query with the constructed WHERE clause
            cursor.execute(query)

            res = [row[0] for row in cursor.fetchall()]
    
    return res

def get_status_values(status_list):
    """Helper function to map status categories to their actual values"""
    updated_category_list = []
    if 'active' in status_list:
        updated_category_list.extend([
            'RECRUITING', 
            'NOT_YET_RECRUITING', 
            'ACTIVE_NOT_RECRUITING', 
            'ENROLLING_BY_INVITATION'
        ])
    if 'completed' in status_list:
        updated_category_list.extend([
            'COMPLETED', 
            'APPROVED_FOR_MARKETING'
        ])
    if 'inactive' in status_list:
        updated_category_list.extend([
            'TERMINATED', 
            'WITHDRAWN', 
            'UNKNOWN', 
            'SUSPENDED', 
            'TEMPORARILY_NOT_AVAILABLE', 
            'NO_LONGER_AVAILABLE'
        ])
    return updated_category_list

def run_es_query(es, filters):
    status_list = filters.status
    study_type = filters.study_type
    phases = filters.phases
    industry_sponsor = filters.industry_sponsor
    mesh_conditions = filters.mesh_condition
    
    query = {
        "_source": [
            "nct_id",
            "brief_title",
            "lead_sponsor_name",
            "interventions",
            "phase",
            "overall_status",
        ],
        "query": {
            "bool": {
                "must": [
                    {
                        "nested": {
                            "path": "interventions",
                            "query": {
                                "bool": {
                                    "must": [
                                        {"exists": {"field": "interventions.name"}},
                                        {"term": {"interventions.type.keyword": "DRUG"}}
                                    ]
                                }
                            }
                        }
                    }
                ]
            }
        }
    }

    if mesh_conditions:
        mesh_condition_query = {
            "nested": {
                "path": "mesh_conditions",
                "query": {
                    "bool": {
                        "should": [
                            {"term": {"mesh_conditions.mesh_term.keyword": condition}}
                            for condition in mesh_conditions
                        ],
                        "minimum_should_match": 1
                    }
                }
            }
        }
        query["query"]["bool"]["must"].append(mesh_condition_query)

    if phases and "All" not in phases:
        phase_query = {
            "bool": {
                "should": [
                    {"term": {"phase.keyword": phase}}
                    for phase in phases
                ],
                "minimum_should_match": 1
            }
        }
        query["query"]["bool"]["must"].append(phase_query)

    if industry_sponsor:
        if industry_sponsor.lower() == 'yes':
            # Include only INDUSTRY sponsors
            industry_query = {
                "term": {
                    "lead_sponsor_class.keyword": "INDUSTRY"
                }
            }
            query["query"]["bool"]["must"].append(industry_query)
        elif industry_sponsor.lower() == 'no':
            # Exclude INDUSTRY sponsors using must_not
            industry_query = {
                "term": {
                    "lead_sponsor_class.keyword": "INDUSTRY"
                }
            }
            # Add must_not if it doesn't exist
            if "must_not" not in query["query"]["bool"]:
                query["query"]["bool"]["must_not"] = []
            query["query"]["bool"]["must_not"].append(industry_query)

    if study_type:
        study_type_query = {
            "term": {
                "study_type.keyword": study_type
            }
        }
        query["query"]["bool"]["must"].append(study_type_query)

    if status_list:
        actual_statuses = get_status_values(status_list)
        if actual_statuses:
            status_query = {
                "bool": {
                    "should": [
                        {"term": {"overall_status.keyword": status}}
                        for status in actual_statuses
                    ],
                    "minimum_should_match": 1
                }
            }
            query["query"]["bool"]["must"].append(status_query)

    print(query)
    response = es.search(
        index="datalake_esindex_clinical_trials",
        body=query,
        size=10_000
    )
    
    # Format the response to get just drug interventions
    trials = []
    drug_dict = {}
    for hit in response['hits']['hits']:
        source = hit['_source']
        phase = source.get('phase', [])
        status = source.get('overall_status', '')
        interventions = source.get('interventions', [])
        
        drug_interventions = [
            intervention['name'] 
            for intervention in interventions
            if intervention.get('type', '').upper() == 'DRUG'
        ]

        for drug in drug_interventions:
            drug_dict[drug.upper()] = drug_dict.get(drug.upper(), 0) + 1

        trial = {
            "trial_id": source['nct_id'],
            "title": source['brief_title'],
            "lead_sponsor_name": source['lead_sponsor_name'],
            "phase": phase,
            "overall_status": status,
            "interventions": drug_interventions,
        }

        trials.append(trial)
    
    sorted_drug_dict = dict(sorted(drug_dict.items(), key=lambda x: x[1], reverse=True))

    return {
        "trials": trials,
        "drug_counts": sorted_drug_dict
    }
