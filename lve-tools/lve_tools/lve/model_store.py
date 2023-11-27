OPENAI_MODELS = {
    "openai/gpt-4": "openai/gpt-4",
    "openai/gpt-3.5-turbo": "openai/gpt-3.5-turbo",
    "openai/gpt-4-vision-preview": "openai/gpt-4-vision-preview",
}

REPLICATE_MODELS = {
    "meta/llama-2-7b-chat": "meta/llama-2-7b-chat:13c3cdee13ee059ab779f0291d29054dab00a47dad8261375654de5540165fb0",
    "meta/llama-2-13b-chat": "meta/llama-2-13b-chat:f4e2de70d66816a838a89eeeb621910adffb0dd0baba3976c96980970978018d",
    "meta/llama-2-70b-chat": "meta/llama-2-70b-chat:02e509c789964a7ea8736978a43525956ef40397be9033abf9fd2badfe68c9e3",

    "mistralai/mistral-7b-instruct-v0.1": "mistralai/mistral-7b-instruct-v0.1:83b6a56e7c828e667f21fd596c338fd4f0039b46bcfa18d973e8e70e455fda70",
}

DUMMY_MODELS = {
    "dummy/dummy": "dummy/dummy",
}

def get_suggested_models():
    models = []
    models += list(OPENAI_MODELS.keys())
    models += list(REPLICATE_MODELS.keys())
    return models