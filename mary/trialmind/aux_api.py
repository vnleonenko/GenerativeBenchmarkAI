import asyncio
import traceback
import httpx
import ftfy
from qdrant_client import QdrantClient, models
import requests
import os
from dotenv import load_dotenv, find_dotenv
import logging

logger = logging.getLogger('my_module_name').setLevel(logging.INFO)
# Silence other loggers
for log_name, log_obj in logging.Logger.manager.loggerDict.items():
    if log_name != 'my_module_name':
        log_obj.disabled = True
# to override existing env.variables        
load_dotenv(find_dotenv(usecwd=True), override=True)

httpx_aclient = httpx.AsyncClient(verify=False,trust_env=False,timeout=600)


async def send_prompt_raw(query, retrieved_docs):
    url = os.getenv("BASE_URL")+"/rerank"
    if 1==1:#'hybrid' in self.vector_store.collection_name:
        docs2 = [ftfy.fix_text(i['page_content']) for i in retrieved_docs]
        logging.info(f'{len(docs2)}, {len(str(docs2))}')
        chunks_idx = [i['metadata']['chunk_number'] for i in retrieved_docs]
        #print(chunks_idx)
    else:
        docs2 = [i.page_content for i in retrieved_docs]
    payload = {
        "model": 'reranker-model',
        "query": query,
        "top_n": 10,
        "documents": docs2,
        "return_documents": False
    }
    #print(url, payload)
    #logging.info(f"number of letters in retr.30 docs: {len(''.join(docs2))}") # ~ 6400
    headers = requests.utils.default_headers()
    headers.update({'User-Agent': 'My User Agent 1.0',})
    '''
    response = requests.post(url, json=payload,  headers=headers,
                             proxies={"http": None, "https": None})
                             '''
    
    response = await httpx_aclient.post(url, json=payload, headers=headers,
                             
                                    )
    response.encoding = 'utf-8'
    logging.info(f"fresh response in asynch: {response.json()['results']}")
    try:
        contents = [docs2[i['index']] for i in response.json()['results']]
        
        contents_idxs = [chunks_idx[i['index']] for i in response.json()['results']]
        #print('contents_idxs', contents_idxs)
    except Exception as e:  
        #print(traceback.format_exc())
        print('exception in rerank: ', e)
        traceback.print_exc()
        contents = []
        contents_idxs = []
    return contents, contents_idxs
    
    
async def rerank_main(queries,docs):
    qs = queries*( int(len(docs)/len(queries)) )
    print(len(docs), len(queries))
    tasks = [send_prompt_raw(q,d) for q,d in zip(qs,docs)]
    logging.info(f" passing {len(tasks)} queries to llama.cpp...")
    
    results = await asyncio.gather(*tasks)
    #print(results)
    return results


def rerank(queries,docs):
    results = asyncio.run(rerank_main(queries,docs))
    return results


def create_hybr_request(doc_id, dense_q, sparse_q,n_to_retrieve):
    filter_q = models.Filter(must=[models.FieldCondition(
                            key="metadata.source",
                            match=models.MatchValue(value=str(doc_id)),
                        ),
                    ]
                )

    
    prefetch = [
            models.Prefetch(
                query=dense_q,
                using="dense",
                limit=round(n_to_retrieve),
                filter=filter_q
            ),
            models.Prefetch(
                query=models.SparseVector(**sparse_q.model_dump()),
                using="sparse",
                limit=round(n_to_retrieve),
                filter=filter_q
            ),
    ]

    query_i = models.QueryRequest(
            prefetch=prefetch,
            query=models.FusionQuery(fusion=models.Fusion.RRF ),
            with_payload=True,
            limit=n_to_retrieve,
    )

    return query_i
    