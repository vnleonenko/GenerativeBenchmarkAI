import pdb
import asyncio
from typing import List, Union
import httpx
from openai import AsyncOpenAI
from openai import AsyncAzureOpenAI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from dotenv import load_dotenv, find_dotenv
import os
import logging
import tenacity
import json
import httpx

OPENAI_MODEL_NAME_GPT4 = "gpt-4-turbo"  # new gpt-4-turbo
OPENAI_MODEL_NAME_GPT35 = "gpt-3.5-turbo"
OPENAI_MODEL_NAME_GPT4o = "gpt-4o"
OPENAI_MODEL_NAME_MAP = {
    "openai-gpt-4": OPENAI_MODEL_NAME_GPT4,
    "openai-gpt-35": OPENAI_MODEL_NAME_GPT35,
    "openai-gpt-4o": OPENAI_MODEL_NAME_GPT4o,
}
httpx_client = httpx.AsyncClient(trust_env=False,verify=False,timeout=600)
# default timeout for AsyncOpenAI requests is 600 (10min)
async_openai_client = AsyncOpenAI(
    base_url=os.getenv("BASE_URL"),
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=7200,
    http_client=httpx_client
)


logger = logging.getLogger('my_module_name').setLevel(logging.INFO)
# Silence other loggers
for log_name, log_obj in logging.Logger.manager.loggerDict.items():
    if log_name != 'my_module_name':
        log_obj.disabled = True
load_dotenv(find_dotenv(usecwd=True))


@tenacity.retry(wait=tenacity.wait_random_exponential(min=5, max=30),
                stop=tenacity.stop_after_attempt(1), 
                #reraise=True
               )
async def api_call_single(client: AsyncOpenAI, model: str, messages: list[dict], temperature: float = 0.0, thinking: bool = False, **kwargs):
    # Call the API
    print(os.getenv("BASE_URL"))#print('\napi_call_single', client.base_url)
    
    print('timeout:', client.timeout)
    if not thinking:
        messages[0]['content'] = '/set nothink '+messages[0]['content']
    
    response = await client.chat.completions.create(
        model=model,
        messages=messages,  # Ensure messages is a list
        temperature=temperature,
        extra_body={"reasoning_effort": "none"},
        **kwargs
    )
    #logging.info(f'fresh: {response}')
    logging.info(f'fresh response in asynch: {response.choices[0].message.content}')
    
    logging.info('')
    return response

from openai import LengthFinishReasonError
CONTINUE_INSTRUCTION = (
    "Your previous response was cut off because it hit the token limit. "
    "Continue generating EXACTLY from the next character after where you "
    "stopped. Do not repeat any earlier text, do not reopen brackets/braces/"
    "keys you already emitted, do not add commentary or markdown code "
    "fences -- output only the raw continuation of the same JSON structure."
)


@tenacity.retry(wait=tenacity.wait_random_exponential(min=5, max=30),
                stop=tenacity.stop_after_attempt(5), 
                #reraise=True
               )
async def api_function_call_single(client: AsyncOpenAI, model: str, messages: list[dict], tools: list[dict], temperature: float = 0.0, thinking: bool = False, **kwargs):
    max_rounds: int = 3
    print(os.getenv("BASE_URL"),model)
    # Call the API
    #logging.info(f"fresh: {messages[0]['content']}")
    convo = messages
    if not thinking:
        messages[0]['content'] = '/set nothink '+messages[0]['content']
    if ('gpt' in model) or ('next' in model):
        reason_e = "low"
    else:
        reason_e = "none"
    try:
        response = await client.chat.completions.parse(
            model=model,
            messages=messages,
            #tools=tools,
            temperature=temperature,
            #extra_body={"structured_outputs": {"json": tools[0]}},
            response_format=tools[0],
            extra_body={"reasoning_effort": reason_e}
            #**kwargs
        )
        logging.info(f'fresh response in asynch: {response.choices[0].message.parsed}')
        logging.info('')
        return response
    
    except LengthFinishReasonError as e:
        # e.completion is the raw (unparsed) ChatCompletion that triggered this
        partial = e.completion.choices[0].message.content or ""
        accumulated_text = partial
        return None

    # --- Rounds 2..N: plain continuation, no response_format --------------
    convo.append({"role": "assistant", "content": partial})
    convo.append({"role": "user", "content": CONTINUE_INSTRUCTION})

    for round_idx in range(2, max_rounds + 1):
        resp = await client.chat.completions.create(
            model=model,
            messages=convo,
            **create_kwargs,
        )
        choice = resp.choices[0]
        piece = choice.message.content or ""
        accumulated_text += piece

        if choice.finish_reason != "length":
            # Done. Validate the stitched-together JSON ourselves.
            try:
                return tools[0].model_validate_json(accumulated_text)
            except Exception as parse_err:
                raise RuntimeError(
                    f"Model finished (finish_reason={choice.finish_reason}) "
                    f"but stitched output failed validation after "
                    f"{round_idx} rounds: {parse_err}\n\n"
                    f"--- accumulated text ---\n{accumulated_text}"
                ) from parse_err

        if round_idx == max_rounds:
            raise RuntimeError(
                f"Still truncated after {max_rounds} rounds "
                f"({len(accumulated_text)} chars accumulated); giving up."
            )

        convo.append({"role": "assistant", "content": piece})
        convo.append({"role": "user", "content": CONTINUE_INSTRUCTION})

    raise RuntimeError("unreachable")

    #logging.info(f'fresh: {response}')
    


async def apply_async(client: AsyncOpenAI, model: str, messages_list: list[list[dict]], **kwargs):
    """
    Apply the OpenAI API asynchronously to a list of messages using high-level asyncio APIs.
    """
    tasks = [api_call_single(client, model, messages, **kwargs) for messages in messages_list]
    logging.info(f" passing {len(tasks)} queries to llama.cpp...")
    results = await asyncio.gather(*tasks)
    return results

async def apply_function_call_async(client: AsyncOpenAI, model: str, messages_list: list[list[dict]], tools: list[dict], **kwargs):
    """
    Apply the OpenAI API asynchronously to a list of messages using high-level asyncio APIs.
    """
    if len(tools)>1:
        tasks = [api_function_call_single(client, model, messages, [tool], **kwargs) for messages, tool in zip(messages_list,tools)]
    else:
        tasks = [api_function_call_single(client, model, messages, tools, **kwargs) for messages in messages_list]
    logging.info(f" passing {len(tasks)} queries to llama.cpp...")
    results = await asyncio.gather(*tasks)
    return results


def fcall(batch_messages, llm, tools, temperature,thinking=False):
    results = asyncio.run(apply_function_call_async(
            client = async_openai_client, 
            model=llm, 
            messages_list=batch_messages, 
            tools=tools, 
            temperature=temperature, 
            seed=0,
            thinking=thinking))
    parsed_results = []
    for result in results:
        try:
            content = result.choices[0].message.content
            parsed_results.append(content)
        except:
            parsed_results.append("")
        #logging.info(f'parsed_results in asynch: {content}')
        #logging.info('')
    return parsed_results


def batch_call_openai(batch_messages, llm, temperature, thinking=False):

    model = llm#OPENAI_MODEL_NAME_MAP.get(llm)
    if model is not None:
        results = _async_execute(
            async_function = apply_async, 
            client = async_openai_client, 
            model=model, 
            messages_list=batch_messages, 
            temperature=temperature, 
            seed=0,
            thinking=thinking
            )
    else:
        raise ValueError(f"Unknown llm: {llm}")

    parsed_results = []
    for result in results:
        try:
            content = result.choices[0].message.content
            parsed_results.append(content)
        except:
            parsed_results.append("")
        #logging.info(f'parsed_results in asynch: {content}')
        #logging.info('')
    return parsed_results

def batch_function_call_openai(batch_messages, llm, tools, temperature,thinking=False):

    model = llm#OPENAI_MODEL_NAME_MAP.get(llm)
    if model is not None:
        results = _async_execute(
            async_function = apply_function_call_async, 
            client = async_openai_client, 
            model=model, 
            messages_list=batch_messages, 
            tools=tools, 
            temperature=temperature, 
            seed=0,
            thinking=thinking
            )
        #print('batch_function_call_openai in asynch',results)
    else:
        raise ValueError(f"Unknown llm: {llm}")
    #print('\nTOOLS: ',tools)
    
    parsed_results = []
    for result in results:
        try:
            #content = result.choices[0].message.content
            content = result.choices[0].message.parsed
            parsed_results.append(content)
        except:
            parsed_results.append("")
        #logging.info(f'parsed_results in asynch: {content}')
        #logging.info('')
    return parsed_results


def _async_execute0(async_function, **kwargs):
    from concurrent.futures import ThreadPoolExecutor
    try:
        loop = asyncio.get_running_loop()
        logging.info(f"!!!!!! 4 !!!!!")
        with ThreadPoolExecutor(4) as executor:
            results = executor.submit(lambda: asyncio.run(async_function(**kwargs)))
            results = results.result()
    except RuntimeError:
        results = async_function(**kwargs)
        results = asyncio.run(results)
    return results

def _async_execute(async_function, **kwargs):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    coro = async_function(**kwargs)

    if loop and loop.is_running():
        # there's a loop
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(coro)
    else:
        # no active loop
        return asyncio.run(coro)
    
def prompts_as_chatcompletions_messages(prompts: List[str]):
    """
    chat messages for the OpenAI GPT4 chat completions API
    """
    conversations = []
    for prompt in prompts:
        messages = [{
            "role": "user",
            "content": prompt
        }]
        conversations.append(messages)

    return conversations