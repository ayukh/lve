import re
from collections import defaultdict 
from lve.prompt import Role

def extract_variables_from_prompt(prompt):
    variables = {}
    for msg in prompt:
        if msg.role == Role.assistant:
            varname = msg.variable
            if varname is None:
                varname = str(len(variables))
            variables[varname] = msg.content
    return variables


class CheckerRegistryHolder(type):

    CHECKER_REGISTRY = {}

    def __new__(cls, name, bases, attrs):
        new_cls = type.__new__(cls, name, bases, attrs)
        if "BaseChecker" not in name:
            cls.CHECKER_REGISTRY[name] = new_cls
        return new_cls

    @classmethod
    def get_checker_registry(cls):
        return dict(cls.CHECKER_REGISTRY)
    


class BaseChecker(metaclass=CheckerRegistryHolder):
    
    def __init__(self, prompt_contains_responses=False, get_variables=False, get_response=True):
        self.prompt_contains_responses = prompt_contains_responses
        self.get_variables = get_variables
        self.get_response = get_response 
        
    def get_args(self, prompt_in, prompt_out, param_values=None):
        """ Extracts a kwargs dictionary from the input and output prompts.
            
            Args:
                prompt_in: The chat corresponding to the input.
                prompt_out: The chat including model responses.
                param_values: The parameter values plugged into the prompt.
            
            Returns:
                kwargs: A dictionary of arguments to be passed to is_safe.
                response_or_variables: If there is only one response, returns the response as string, else returns all variables as a dictionary.
        """
        kwargs = {}
        kwargs["prompt"] = prompt_in if self.prompt_contains_responses else prompt_out
        cnt_variables = sum(p.role == Role.assistant for p in prompt_out)
        response = prompt_out[-1].content
        response_or_variables = response

        if self.get_response:
            kwargs["response"] = response

        if self.get_variables or cnt_variables > 1:
            variables = extract_variables_from_prompt(prompt_out) 
            if self.get_variables:
                kwargs["variables"] = variables  
            if cnt_variables > 1:
                response_or_variables = variables

        kwargs["param_values"] = param_values
        return kwargs, response_or_variables
        
    def invoke_check(self, prompt_in, prompt_out, param_values=None):
        """ Calls the correct signature of is_safe based on the configuration.
            Main function exposed to the lve internals, but not the user.
            
            Args:
                prompt_in: The chat corresponding to the input.
                prompt_out: The chat including model responses.
                param_values: The parameter values plugged into the prompt.
            
            Returns:
                is_safe: Whether the response is safe as determined by is_safe.
                response_or_variables: If there is only one response, returns the response as string, else returns all variables as a dictionary.
        """
        kwargs, response_or_variables = self.get_args(prompt_in, prompt_out, param_values)
        return self.is_safe(**kwargs), response_or_variables

    def is_safe(self, prompt, response, param_values=None) -> bool:
        """Determines whether the response is safe given the prompt and the parameters.

        Args:
            prompt: The prompt corresponding to the test.
            response: The response generated by the model.
            param_values: The parameter values plugged into the prompt.
        """
        raise NotImplementedError

    def postprocess_response(self, response):
        """Postprocess response (e.g. to remove bad words or PII)

        Args:
            response: The response generated by the model.
        """
        return response
    
    # meta information about the checker

    @classmethod
    def has_post_processing(cls):
        """Whether the checker has post processing."""
        return not cls.postprocess_response.__code__ == BaseChecker.postprocess_response.__code__

    @classmethod 
    def is_multi_run(cls):
        """Whether the checker is a multi-run checker."""
        return False

    @classmethod
    def is_multi_variable(cls):
        """Whether the checker is a multi-variable checker."""
        return False

class LambdaChecker(BaseChecker):
    """
    Checker which uses a lambda function to check safety.

    **Attributes**

    - *func*: The lambda function to be executed. Should return a `bool`.
    """

    def __init__(self, func):
        super().__init__()
        self.func = eval(func)
        
    def is_safe(self, prompt, response, param_values) -> bool:
        return self.func(response, **param_values)

class RegexChecker(BaseChecker):
    """
    Checker which judges safety based on whether the response matches given pattern.

    **Attributes**    

    - *pattern*: The regex pattern.
    - *match_safe*: The value of the match to be compared against.
    - *flags*: A string containing one Regex Flag. Currently only `A`, `I`, `L`, `M`, `DOTALL` are supported. Defaults to 0 (no flag).
    """

    def get_flag(self, flag):
        if flag == "A" or flag == "ASCII":
            return re.ASCII
        elif flag == "I" or flag == "IGNORECASE":
            return re.IGNORECASE
        elif flag == "L" or flag == "LOCALE":
            return re.LOCALE
        elif flag == "M" or flag == "MULTILINE":
            return re.MULTILINE
        elif flag == 'DOTALL':
            return re.DOTALL
        
        raise ValueError(f"Unknown regex flag {flag}")

    def __init__(self, pattern, match_safe, flags=0):
        super().__init__()
        
        if flags != 0:
            flags = self.get_flag(flags)

        self.pattern = re.compile(pattern, flags=flags)
        self.match_safe = match_safe
    
    def is_safe(self, prompt, response, param_values) -> bool:
        matches = self.pattern.search(response) is not None
        return matches == self.match_safe

class MultiRunBaseChecker(BaseChecker):
    
    def invoke_check(self, prompts_in, prompts_out, param_values=None):
        """ Calls the correct signature of is_safe based on the configuration.
            Main function exposed to the lve internals, but not the user.
            
            Args:
                prompts_in: List of the chats corresponding to the inputs.
                prompts_out: List of the chats including the model responses. Order should match prompts_in.
                param_values: The parameter values plugged into the prompt.
            
            Returns:
                is_safe: Whether the response is safe as determined by is_safe.
                response_or_variables: List of responses or variable sets to return.
        """
        assert len(prompts_in) == len(prompts_out)
        responses = []
        args = defaultdict(list)
        for i in range(len(prompts_in)):
            kwargs, response_or_variables = self.get_args(prompts_in[i], prompts_out[i], param_values)
            for k, v in kwargs.items():
                if k != "param_values":
                    args[k].append(v)
            responses.append(response_or_variables)
        if param_values is not None:
            args["param_values"] = param_values
        return self.is_safe(**args), responses

    def is_safe(self) -> bool:
        """Determines whether the response is safe given the prompt and the parameters as a list over all instances.
        """
        raise NotImplementedError

    @classmethod 
    def is_multi_run(cls):
        return True
    
class MultiRunLambdaChecker(MultiRunBaseChecker):
    """
    Checker which uses a lambda function to check safety.

    **Attributes**

    - *func*: The lambda function to be executed. Should return a `bool`.
    """

    def __init__(self, func):
        super().__init__()
        self.func = eval(func)
        
    def is_safe(self, prompt, response, param_values) -> bool:
        return self.func(response, **param_values)


