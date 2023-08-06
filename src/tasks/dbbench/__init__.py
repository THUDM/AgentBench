import json
import re
from typing import Callable, Dict, List, Any

import multiprocess as mp

from src.task import Task, Dataset, DataPiece, Session
from .Interaction import Container

big_prompt = """
I will ask you a question, then you should help me operate a MySQL database with SQL to answer the question.
You have to explain the problem and your solution to me and write down your thoughts.
After thinking and explaining thoroughly, every round you can choose to operate or to answer.
your operation should be like this:
Action: Operation
```sql
SELECT * FROM table WHERE condition;
```
You MUST put SQL in markdown format without any other comments. Your SQL should be in one line.
Every time you can only execute one SQL statement. I will only execute the statement in the first SQL code block. Every time you write a SQL, I will execute it for you and give you the output.
If you are done operating, and you want to commit your final answer, then write down:
Action: Answer
Final Answer: ["ANSWER1", "ANSWER2", ...]
DO NOT write this pattern unless you are sure about your answer. I expect an accurate and correct answer.
Your answer should be accurate. Your answer must be exactly the same as the correct answer.
If the question is about modifying the database, then after done operation, your answer field can be anything.
If your response cannot match any pattern I mentioned earlier, you will be judged as FAIL immediately.
Your input will be raw MySQL response, you have to deal with it by yourself.
"""


def build_sql(entry, conn):
    name = entry["table"]["table_name"]
    columns = ",".join(
        [f"`{escape(column['name'], conn)}` TEXT" for column in entry["table"]["table_info"]["columns"]])
    column_names = ",".join(
        [f"`{escape(column['name'], conn)}`" for column in entry["table"]["table_info"]["columns"]])
    items = []
    for row in entry["table"]["table_info"]["rows"]:
        item = "("
        for col in row:
            item += f"'{escape(col, conn)}',"
        item = item[:-1] + ")"
        items.append(item)
    items = ",".join(items)
    sql = f"""CREATE DATABASE IF NOT EXISTS `{name}`;
USE `{name}`;
CREATE TABLE IF NOT EXISTS `{name}` ({columns});
INSERT INTO `{name}` ({column_names}) VALUES {items}; 
COMMIT;
"""
    return sql


def escape(string: str, conn):
    if type(string) is not str:
        string = str(string)
    return conn._cmysql.escape_string(string).decode("utf-8")


def process(receiver, max_round):
    container = Container()
    while True:
        data_item, session, sender = receiver.recv()

        if data_item is None and session is None and sender is None:
            break

        entry = data_item
        # container = self.container
        init = build_sql(entry, container.conn)
        container.execute(init)
        db = entry['table']['table_name']
        session.inject({"role": "user", "content": big_prompt})
        session.inject({"role": "agent", "content": "Ok."})
        prompt = entry["description"] + "\n" + entry["add_description"]
        session.inject({"role": "user", "content": prompt})
        res = session.action()
        try:
            action = re.search(r"Action: (.*?)\n", res)
            rounds = 0
            while action and action.group(1) == "Operation" and rounds < max_round:
                res = re.search(r"```sql\n([\s\S]*?)\n```", res)
                if not res:
                    answer = ""
                    break
                sql = res.group(1).strip()
                sql = sql.replace("\n", " ")
                response = container.execute(sql, db)
                if response:
                    session.inject({"role": "user", "content": response})
                else:
                    session.inject({"role": "user", "content": ""})
                res = session.action()
                action = re.search(r"Action: (.*?)\n", res)
                rounds += 1
            else:
                answer = re.search(r"\nFinal Answer:(.*)", res)
                if answer:
                    answer = answer.group(1)
                else:
                    answer = ""
        except Exception as e:
            error = str(e)
            answer = ""
        else:
            error = ""
        if data_item["type"][0] in ("INSERT", "DELETE", "UPDATE"):
            columns = ",".join([f"`{escape(column['name'], container.conn)}`"
                                for column in entry["table"]["table_info"]["columns"]])
            md5_query = f"select md5(group_concat(rowhash order by rowhash)) as hash " \
                        f"from( SELECT substring(MD5(CONCAT_WS(',', {columns})), 1, 5) AS rowhash FROM `{db}`) as sub;"
            answer = container.execute(md5_query, db)
        container.execute(f"drop database `{db}`")
        sender.send({
            "answer": str(answer),
            "type": entry["type"][0],
            "history": session.history,
            "error": error,
        })
    container.delete()


class DBBench(Task[Dict, Dict[str, Any], str]):
    def __init__(self, **configs):
        super().__init__(**configs)
        self.data_file = configs.pop("data_file")
        self.max_round = configs.pop("max_round", 5)
        self.processes = []
        ctx = mp.get_context('spawn')
        for i in range(self.workers):
            receiver, sender = ctx.Pipe(False)
            p = ctx.Process(target=process, args=(receiver, self.max_round))
            p.start()
            self.processes.append((sender, ctx.Lock(), p))

    def escape(self, string: str, conn=None):
        conn = conn or self.conn
        if type(string) is not str:
            string = str(string)
        return conn._cmysql.escape_string(string).decode("utf-8")

    def get_data(self) -> Dataset[Dict, str]:
        dataset = Dataset()
        with open(self.data_file) as f:
            if self.data_file.endswith("json"):
                data = json.loads(f.read())
            else:
                data = [json.loads(line) for line in f.readlines()]

        for entry in data:
            if entry["type"][0] in ("INSERT", "DELETE", "UPDATE"):
                ans = entry.pop("answer_md5")
            else:
                ans = entry.pop("label")
            inp = entry
            dataset.append(DataPiece(inp, ans))

        return dataset

    def predict_single(self, session: Session, data_item: Dict) -> Dict[str, Any]:
        ctx = mp.get_context('spawn')
        receiver, sender = ctx.Pipe(False)
        i = 0
        while True:
            if self.processes[i][1].acquire(timeout=0.2):
                break
            i += 1
            i %= self.workers
        self.processes[i][0].send((data_item, session, sender))
        ret = receiver.recv()
        self.processes[i][1].release()
        return ret

    @property
    def metrics(self) -> Dict[str, Callable[[List[Dict[str, Any]], List[str]], float]]:
        def factory(typ):
            def acc(inp: List[Dict[str, Any]], tar: List[str]) -> float:
                correct = 0
                total = 0
                for entry, cor in zip(inp, tar):
                    if not entry:
                        continue
                    ans, t = entry["answer"], entry["type"]
                    if t != typ and not (typ == "SELECT" and t not in ("INSERT", "UPDATE")):
                        continue
                    if t in ("INSERT", "DELETE", "UPDATE"):
                        correct += ans == cor
                    else:
                        try:
                            ans = list(eval(ans))
                        except:
                            ans = [ans]
                        if len(ans) == 1 and len(cor) == 1:
                            try:
                                correct += float(ans[0]) == float(cor[0])
                            except (ValueError, TypeError):
                                correct += ans[0] == cor[0]
                            else:
                                print(ans, cor)
                        else:
                            try:
                                cor = set(cor)
                                ans = set(ans)
                                correct += ans == cor
                            except:
                                pass
                    total += 1
                if total == 0:
                    print(f"WARNING: {typ} does not exist!")
                    return 0
                return correct / total

            return acc

        types = ['other', 'counting', 'comparison', 'ranking', 'aggregation-SUM', 'aggregation-MIN', 'aggregation-MAX',
                 'aggregation-AVG', 'SELECT', 'INSERT', 'UPDATE']

        ret = {}
        for typ in types:
            ret[typ + "_accuracy"] = factory(typ)

        ret["overall_cat_accuracy"] = lambda inp, tar: sum([ret[typ + "_accuracy"](inp, tar)
                                                            for typ in ("SELECT", "INSERT", "UPDATE")]) / 3

        def average_round(inp: List[Dict[str, Any]], tar: List[str]) -> float:
            count = 0
            total = 0
            for entry, cor in zip(inp, tar):
                if not entry:
                    continue
                count += len(entry["history"])
                total += 1
            return count / total if total else 0, total

        ret["average_round"] = average_round

        return ret

    def release(self):
        for sender, _, _ in self.processes:
            sender.send((None, None, None))
        for _, _, p in self.processes:
            p.join()
