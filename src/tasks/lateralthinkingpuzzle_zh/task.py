from src.task import Task, Dataset, DataPiece
from src import YAMLConfig
import pandas as pd
from nltk.translate.bleu_score import sentence_bleu

rules_solver = "1. 游戏的开始你会获得一段隐去关键信息的叙述，即汤面，你要根据汤面提出问题，问题需要能够通过“是”、“否”或“无关”来回答。\n2. 你通过提问缩小真相的范围，直到最终猜到真相（即汤底）。\n3. 你每次只能提一个问题。\n4. 记住你的身份是玩家，不可以擅自宣布游戏结束，不可以放弃推理，也不可以要求出新的游戏题目。\n5. 你不能直接重复汤面中已有的信息。\n6. 你不能直接用为什么的形式询问汤面的细节，需要你自己猜测。\n7. 你不能直接询问汤底，需要自己推测。"
content_solver = f"你是一个游戏玩家，你在玩一个横向推理游戏，名叫情境猜谜，也叫海龟汤。\n海龟汤是一个推理类游戏，以下是游戏规则：\n{rules_solver}\n\n接下来，请充分利用以上信息，进行游戏推理，注意你的提问需要是能用“是”、“否”或“无关”回答的问题，每次只能提一个问题。"
rules = "1. 你知道汤面和汤底，当用户需要玩海龟汤时，给予用户汤面，用户只知道汤面，不知道汤底。\n2. 用户提出可以用“是”、“否”、“无关”来回答的问题，用户提问是为了猜测到汤底，你根据汤底回答用户的提问，只能用“是”、“否”或“无关”回答用户，从而引导用户猜到正确的汤底。\n3. 如果用户直接以“为什么”的形式询问汤面的细节，请告知用户需要自己猜测。\n4. 你要充分理解和准确解读汤底的信息，根据汤底的信息和用户过往提问信息对用户的提问做出回答，用户的提问不一定包含汤底的信息，但是你的回答必须符合汤底的事实。\n5. 只有在汤底无法提供直接或间接的答案时，你才可以回答“无关”，注意这是回答“无关”的唯一条件，其他时候你要回答“是”或“否”。\n6. 你不能直接将汤底的信息告诉用户，就算用户直接问也不行。\n7. 要整体判断用户的提问，理解用户整体的意思，不可片面通过某一个点作答，所答必须符合汤底事实。\n8. 当用户在猜测汤底的过程中，猜到部分真相但与汤底的完整真相还有差距时，你可以提供一定的切入点提示，但不能直接透露汤底的信息。"

class LateralThinkingPuzzle_zh(Task):
    def __init__(self, **configs):
        self.round = configs.pop("round", 50)
        self.filepath = configs.pop("filepath", None)
        self.eval_yaml = configs.pop("eval_yaml", None)
        self.eval_agent = YAMLConfig.create_from_yaml(self.eval_yaml)
        super().__init__(**configs)

    @property
    def metrics(self):
        return {"main": lambda outputs, targets: sum([output['progress'] for output in outputs if output])/len([output['accuracy'] for output in outputs if output]),
                "SGA": lambda outputs, targets: sum([output['accuracy'] for output in outputs if output])/len([output['accuracy'] for output in outputs if output]),
                "RE": lambda outputs, targets: sum([output['efficiency'] for output in outputs if output])/len([output['accuracy'] for output in outputs if output]),
                "QR": lambda outputs, targets: sum([output['relevance'] for output in outputs if output])/len([output['accuracy'] for output in outputs if output]),
                "GP": lambda outputs, targets: sum([output['progress'] for output in outputs if output])/len([output['accuracy'] for output in outputs if output])}

    def get_data(self):
        data = Dataset()
        table = pd.read_excel(self.filepath)
        for i in range(table.values.shape[0]):
            story = table.values[i, 0].strip()
            answer = table.values[i, 1].strip()
            story_key = table.values[i, 2].strip()
            answer_key = table.values[i, 3].strip()
            data.append(DataPiece((story, answer, story_key, answer_key), answer))
        return data

    def predict_single(self, session, data_item): # return OUTPUT object, need to be json serializable
        story, answer, story_key, answer_key = data_item[0], data_item[1], data_item[2], data_item[3]
        host = f"{content_solver}\n以下是你的汤面：\n{story}\n\n你可以开始猜测汤底的内容，我会回答你的问题。请注意，我只能回答“是”或“否”。"
        results = {}
        correct = 0
        relevance = 0
        finished = False
        logs = []
        logs.append(f'汤面：{story}')
        logs.append(f'汤底：{answer}')
        hit_keys = {}
        prim_prompt = f"我需要你做一个游戏的主持人，游戏名叫海龟汤。\n\n海龟汤游戏由汤面和汤底组成，你的汤面是：“{story}”\n你的汤底是：“{answer}”\n\n游戏规则：\n{rules}\n\n游戏过程中，请你用以上游戏规则约束你的行为，因为这样可以为用户带来良好的游戏体验。仔细审题，确保回答符合游戏规则和汤底的信息，当用户发出游戏请求时，给出汤面，并通过回答“是”、“否”或“无关”帮助用户猜到汤底。注意每次回答你都必须确保自己充分理解并遵守了以上游戏规则和你的汤面及汤底，保证用户体验，不要出现无法回答的情况，更不要违反游戏规则。"
        hosting = [
            {"role": "user", "content": prim_prompt},
            {"role": "assistant", "content": "好的，我明白自己的角色是海龟汤游戏的主持人，要通过回答用户的问题帮助用户猜到汤底。我已充分理解汤面和汤底的所有信息，并认真阅读了所有规则，保证自己会在游戏过程中遵守所有规则。"},
            {"role": "user", "content": "请总结汤面的关键点，以确保你理解了汤面。"},
            {"role": "assistant", "content": story_key},
            {"role": "user", "content": "请总结汤底的关键点，以确保你理解了汤底。"},
            {"role": "assistant", "content": answer_key},
            {"role": "user", "content": "请复述一遍规则，以确保你理解了所有规则。"},
            {"role": "assistant", "content": rules},
            {"role": "user", "content": "好的，我们现在可以开始游戏了。记住，每次回答前你要回顾汤面的关键点、汤底的关键点、规则，回答是或否或无关。"},
            {"role": "assistant", "content": f"好的，作为游戏的主持人，我将遵守以上规则，并确保回答符合规则和汤底的信息。下面是你的汤面：\n{story}\n\n你可以开始猜测汤底的内容，我会回答你的问题。请注意，你的问题需要能够用“是”、“否”或“无关”来回答。"},
        ]
        story_key = story_key.split('\n')
        answer_key = answer_key.split('\n')
        hints = len(answer_key)
        history = []
        known = []
        reasoning = []
        bingo = 0
        abort = 0
        finish_round = self.round
        for i in range(self.round):
            solver = session.action({"role": "user", "content": host})
            solver = solver.strip().split('\n')[0].strip()
            logs.append(f'第{i+1}轮：{solver}')
            if '感谢' in solver or '谢谢' in solver or '再见' in solver:
                abort += 2
                host = '请你继续根据汤面猜测汤底的信息，提出一个可以用“是”或“否”或“无关”回答的问题。'
                logs.append(host)
                if abort >= 5:
                    break
                continue

            llm = True
            for key in story_key:
                key = key.strip()
                if key == '':
                    continue
                if ' ' in key:
                    key = key.split(' ')[1]
                bleu = sentence_bleu([key], solver.replace('？', '。'), weights=(1, 0, 0, 0))
                if bleu > 0.85:
                    host = '这是汤面中已有的信息，请提一个新问题。'
                    llm = False
                    break
            if llm:
                for key in history:
                    key = key.strip()
                    if key == '':
                        continue
                    if ' ' in key:
                        key = key.split(' ')[1]
                    bleu = sentence_bleu([key], solver.replace('？', '。'), weights=(1, 0, 0, 0))
                    if bleu > 1:
                        host = '这是已经提问过的内容，请提一个新问题。'
                        llm = False
                        abort += 1
                        break
            if abort >= 5:
                break

            if llm:
                history.append(solver.replace('？', '。'))
                hosting = hosting[:10]
                if len(known) > 0:
                    hosting += [{"role": 'user', "content": f"{' '.join(known)}\n请回答是或否或无关。"}, {"role": "assistant", "content": '是。'}, {"role": 'user', "content": f"{solver}\n请回答是或否或无关。"}]
                else:
                    hosting += [{"role": 'user', "content": f"{solver}\n请回答是或否或无关。"}]
                host = self.eval_agent.inference(hosting).strip()
                if '感谢' in host or '谢谢' in host or '再见' in host:
                    abort += 2
                    logs.append(host)
                    if abort >= 5:
                        break
                    continue
                relevant = False
                if host.startswith("是"):
                    correct += 1
                    summary = self.eval_agent.inference([{"role": "user", "content": f"请将以下内容转述为陈述句，并简化为一句话：\n{solver}"}]).strip()
                    relevant = True
                elif host.startswith("不是") or host.startswith("否"):
                    summary = self.eval_agent.inference([{"role": "user", "content": f"请将以下内容取反义然后转述为陈述句，并简化为一句话：\n{solver}"}]).strip()
                    relevant = True
                if relevant:
                    relevance += 1
                    history.append(summary)
                    known.append(summary)
                    reasoning.append(summary)
                    if len(reasoning) >= 2:
                        merge = self.eval_agent.inference([{"role": "user", "content": f"请将以下内容简化为一句话：\n{' '.join(reasoning)}"}]).strip()
                    else:
                        merge = summary
                    for key in answer_key:
                        key = key.strip()
                        if key == '':
                            continue
                        if ' ' in key:
                            key1 = key.split(' ')[1]
                        else:
                            key1 = key
                        if len(solver.replace('？', '')) < len(key1):
                            continue
                        comp_msg = [{"role": "user", "content": f"请对比第一句话和第二句话之间的信息，判断第二句话是否完整地概括了第一句话的全部信息，包括关键细节和描述。请用是或否回答。\n第一句话：{key1}\n第二句话：{merge}"}]
                        compare = self.eval_agent.inference(comp_msg).strip()
                        if compare.startswith('是'):
                            bingo += 1
                            answer_key.remove(key)
                            reasoning = []
                            hit_keys[key1] = merge
                            break
                    if bingo >= len(answer_key) and not finished:
                        finished = True
                        finish_round = i+1
            logs.append(host)
        results['accuracy'] = correct / self.round
        results['efficiency'] = 1-(finish_round)/self.round
        results['relevance'] = relevance / self.round
        results['progress'] = bingo/hints
        results['finish_round'] = finish_round
        results['finished'] = finished
        results['hit_keys'] = hit_keys
        results['history'] = logs
        return results