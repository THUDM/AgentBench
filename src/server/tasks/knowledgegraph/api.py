import json
import re
from os.path import dirname, join
from typing import Union

from .utils.logic_form_util import postprocess_raw_code, lisp_to_sparql, range_info
from .utils.sparql_executer import SparqlExecuter

# Load ontology vocab
with open(join(dirname(__file__), 'ontology', 'vocab.json')) as f:
    vocab = json.load(f)
    attributes = vocab["attributes"]
    relations = vocab["relations"]

# Global caches (kept for compatibility with older code paths)
variable_relations_cache = {}
variable_attributes_cache = {}
relation_cache = {}
attribute_cache = {}


class Variable:

    def __init__(self, type, program):
        self.type = type
        self.program = program

    def __hash__(self) -> int:
        return hash(self.program)

    def __eq__(self, __value: object) -> bool:
        if isinstance(__value, Variable):
            return self.program == __value.program
        else:
            return False

    def __repr__(self) -> str:
        return self.program


class API:

    def __init__(self, sparql_executor: SparqlExecuter, task_id: int = 0):
        self.sparql_executor = sparql_executor
        self.task_id = task_id

    def final_execute(self, variable: Variable):
        program = variable.program
        processed_code = postprocess_raw_code(program)
        sparql_query = lisp_to_sparql(processed_code)
        results = self.sparql_executor.execute_query(sparql_query)
        return results

    def get_relations(self, variable: Union[Variable, str]):
        """
        Get all relations of a variable (variable = program derivation or entity id).
        Returns (None, "Observation: [...]").
        """
        if not isinstance(variable, Variable):
            if not re.match(r'^([mf])\.[\w_]+$', variable):
                raise ValueError("get_relations: variable must be a variable or an entity")

        cache_key = (self.task_id, variable if isinstance(variable, str) else hash(variable))

        if cache_key in relation_cache:
            out_relations = relation_cache[cache_key]
        else:
            if isinstance(variable, Variable):
                program = variable.program
                processed_code = postprocess_raw_code(program)
                sparql_query = lisp_to_sparql(processed_code)

                clauses = sparql_query.split("\n")
                new_clauses = [clauses[0], "SELECT DISTINCT ?rel\nWHERE {\n?x ?rel ?obj .\n{"]
                new_clauses.extend(clauses[1:])
                new_clauses.append("}\n}")
                new_query = '\n'.join(new_clauses)

                out_relations = self.sparql_executor.execute_query(new_query)
            else:
                out_relations = self.sparql_executor.get_out_relations(variable)

            out_relations = list(set(out_relations).intersection(set(relations)))
            relation_cache[cache_key] = out_relations

        rtn_str = f"Observation: [{', '.join(out_relations)}]"
        variable_relations_cache[variable] = out_relations
        return None, rtn_str

    def get_neighbors(self, variable: Union[Variable, str], relation: str):
        """
        Get neighbors via a relation. Returns (new_variable, "Observation: ...").
        """
        if not isinstance(variable, Variable):
            if not re.match(r'^([mf])\.[\w_]+$', variable):
                raise ValueError("get_neighbors: variable must be a variable or an entity")

        cache_key = (self.task_id, variable if isinstance(variable, str) else hash(variable))
        if cache_key not in relation_cache and variable not in variable_relations_cache:
            self.get_relations(variable)

        relations_to_check = variable_relations_cache.get(variable, [])
        if relation not in relations_to_check:
            raise ValueError("get_neighbors: relation must be a relation of the variable")

        rtn_str = f"Observation: variable ##, which are instances of {range_info[relation]}"
        base_program = variable.program if isinstance(variable, Variable) else variable
        new_variable = Variable(
            range_info[relation],
            f"(JOIN {relation + '_inv'} {base_program})"
        )
        return new_variable, rtn_str

    def intersection(self, variable1: Variable, variable2: Variable):
        """
        Set intersection. Returns (new_variable, "Observation: ...").
        """
        if variable1.type != variable2.type:
            raise ValueError("intersection: two variables must have the same type")
        if not isinstance(variable1, Variable) or not isinstance(variable2, Variable):
            raise ValueError("intersection: variable must be a variable")

        rtn_str = f"Observation: variable ##, which are instances of {variable1.type}"
        new_variable = Variable(variable1.type, f"(AND {variable1.program} {variable2.program})")
        return new_variable, rtn_str

    def union(self, variable1: Variable, variable2: Variable):
        """
        Set union. Returns (new_variable, "Observation: ...").
        """
        if variable1.type != variable2.type:
            raise ValueError("union: two variables must have the same type")
        if not isinstance(variable1, Variable) or not isinstance(variable2, Variable):
            raise ValueError("union: variable must be a variable")

        rtn_str = f"Observation: variable ##, which are instances of {variable1.type}"
        new_variable = Variable(variable1.type, f"(OR {variable1.program} {variable2.program})")
        return new_variable, rtn_str

    def count(self, variable: Variable):
        """
        Count variable cardinality. Returns (new_variable(number), "Observation: ...").
        """
        rtn_str = f"Observation: variable ##, which is a number"
        new_variable = Variable("type.int", f"(COUNT {variable.program})")
        return new_variable, rtn_str

    def get_attributes(self, variable: Variable):
        """
        Get all attributes of a variable.
        Returns (None, "Observation: [...]").
        """
        cache_key = (self.task_id, hash(variable))

        if cache_key in attribute_cache:
            out_relations = attribute_cache[cache_key]
        else:
            program = variable.program
            processed_code = postprocess_raw_code(program)
            sparql_query = lisp_to_sparql(processed_code)

            clauses = sparql_query.split("\n")
            new_clauses = [clauses[0], "SELECT DISTINCT ?rel\nWHERE {\n?x ?rel ?obj .\n{"]
            new_clauses.extend(clauses[1:])
            new_clauses.append("}\n}")
            new_query = '\n'.join(new_clauses)

            out_relations = self.sparql_executor.execute_query(new_query)
            out_relations = list(set(out_relations).intersection(set(attributes)))
            attribute_cache[cache_key] = out_relations
            variable_attributes_cache[variable] = out_relations

        rtn_str = f"Observation: [{', '.join(out_relations)}]"
        return None, rtn_str

    def argmax(self, variable: Variable, attribute: str):
        """
        Argmax by attribute. Returns (new_variable, "Observation: ...").
        """
        cache_key = (self.task_id, hash(variable))
        if cache_key not in attribute_cache and variable not in variable_attributes_cache:
            self.get_attributes(variable)

        if attribute not in variable_attributes_cache.get(variable, []):
            raise ValueError("argmax: attribute must be an attribute of the variable")

        rtn_str = f"Observation: variable ##, which are instances of {variable.type}"
        new_variable = Variable(variable.type, f"(ARGMAX {variable.program} {attribute})")
        return new_variable, rtn_str

    def argmin(self, variable: Variable, attribute: str):
        """
        Argmin by attribute. Returns (new_variable, "Observation: ...").
        """
        cache_key = (self.task_id, hash(variable))
        if cache_key not in attribute_cache and variable not in variable_attributes_cache:
            self.get_attributes(variable)

        if attribute not in variable_attributes_cache.get(variable, []):
            raise ValueError("argmin: attribute must be an attribute of the variable")

        rtn_str = f"Observation: variable ##, which are instances of {variable.type}"
        new_variable = Variable(variable.type, f"(ARGMIN {variable.program} {attribute})")
        return new_variable, rtn_str
