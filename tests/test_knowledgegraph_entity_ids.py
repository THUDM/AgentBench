import unittest

from src.server.tasks.knowledgegraph import api as knowledgegraph_api


class StubSparqlExecutor:
    def __init__(self):
        self.entities = []

    def get_out_relations(self, entity):
        self.entities.append(entity)
        return []


class KnowledgeGraphEntityIdTest(unittest.TestCase):
    def setUp(self):
        knowledgegraph_api.relation_cache.clear()
        knowledgegraph_api.variable_relations_cache.clear()
        self.executor = StubSparqlExecutor()
        self.api = knowledgegraph_api.API(self.executor)

    def test_get_relations_accepts_g_prefixed_entity(self):
        entity = "g.11b5lzm6b0"

        self.api.get_relations(entity)

        self.assertEqual(self.executor.entities, [entity])

    def test_get_neighbors_accepts_g_prefixed_entity(self):
        entity = "g.11b5lzm6b0"
        relation = "test.relation"
        knowledgegraph_api.variable_relations_cache[entity] = [relation]
        knowledgegraph_api.range_info[relation] = "test.type"
        self.addCleanup(knowledgegraph_api.range_info.pop, relation)

        variable, _ = self.api.get_neighbors(entity, relation)

        self.assertEqual(variable.program, f"(JOIN {relation}_inv {entity})")

    def test_f_prefixed_value_is_rejected(self):
        with self.assertRaises(ValueError):
            self.api.get_relations("f.not_an_entity")
        with self.assertRaises(ValueError):
            self.api.get_neighbors("f.not_an_entity", "test.relation")


if __name__ == "__main__":
    unittest.main()
