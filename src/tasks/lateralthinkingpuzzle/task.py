from src.task import Task, Dataset, DataPiece
from src import YAMLConfig
import pandas as pd
from nltk.translate.bleu_score import sentence_bleu

rules_solver = '1. At the beginning of the game, you will receive a narrative, referred to as "story". Based on the story, you need to ask questions that can be answered with "yes", "no", or "irrelevant" to guees out the "truth".\n2. By asking questions, you narrow down the range of possibilities until you eventually guess out the truth.\n3. Each time, you can only ask one question.\n4. Remember that your role is a player. You cannot declare the end of the game, give up on reasoning, or request a new game.\n5. You cannot directly repeat information already provided in the story.\n6. You cannot directly ask for details about the story in the form of "why" questions; you need to make your own guesses for truth.\n7. You cannot directly inquire about the story; you must make your own deductions.'
content_solver = f'You are a game player, and you are playing Lateral Thinking Puzzle, also known as Situation Puzzle.\nLateral Thinking Puzzle is a deductive reasoning game, and here are the game rules:\n{rules_solver}\n\nNext, please make full use of the information provided above to engage in game reasoning. Keep in mind that your questions should be answerable with "yes", "no", or "irrelevant", and you can only ask one question at a time.'
rules = '1. You know both the "story" and the "truth". When a user wants to play Lateral Thinking Puzzle, you provide them with the "story". The user only knows the "story" and is unawared of the "truth".\n2. The user asks questions that can be answered with "yes," "no," or "irrelevant". Their questions are aimed at guessing the "truth". Based on the "truth", you respond to the user\'s questions using "yes," "no," or "irrelevant" to guide them towards guessing the correct truth.\n3. If the user directly asks for details about the truth using the form of "why" questions, inform them that they need to make their own guesses.\n4. You must fully understand and accurately interpret the information from the truth. Based on the information of the truth and the user\'s past questions, you answer the user\'s questions. The user\'s questions may not necessarily contain information from the truth, but your responses must align with the facts of the truth.\n5. You can only answer "irrelevant" when the truth cannot provide a direct or indirect answer. Note that this is the only condition for responding "irrelevant"; otherwise, you should answer "yes" or "no."\n6. You cannot directly disclose the information from the truth to the user, even if they ask directly.\n7. You need to judge the user\'s questions as a whole and understand their overall intent. Avoid answering based solely on a particular point; your responses must align with the facts of the truth.\n8. During the user\'s process of guessing the truth, if they come close to some truths but still have gaps in understanding the complete truth of the truth, you can provide certain entry point hints. However, you cannot directly reveal information from the truth.'

class LateralThinkingPuzzle(Task):
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
        host = f"{content_solver}\nHere is your story:\n{story}\n\nYou can start guessing the content of the truth, and I will answer your questions. Please note that your questions should be answerable with \"yes\", \"no\", or \"irrelevant\"."
        results = {}
        correct = 0
        relevance = 0
        finished = False
        logs = []
        logs.append(f'Story: {story}')
        logs.append(f'Truth: {answer}')
        hit_keys = {}
        prim_prompt = f"I need you to be the host of a game called Lateral Thinking Puzzle.\n\nLateral Thinking Puzzle is a game consist of a story and a truth. Your story is: '{story}'\nYour truth is: '{answer}'\n\nHere are the game rules:\n{rules}\n\nDuring the game process, please adhere to the above game rules to ensure a positive gaming experience for the users. Pay close attention to the questions asked and ensure that your responses comply with both the game rules and the information from the truth. When a user requests to play the game, provide them with the story and help them guess the truth by answering with \"yes\", \"no\", or \"irrelevant\". Remember that with each response, you must fully understand and abide by the aforementioned game rules, as well as the story and the truth. This will ensure a smooth user experience and avoid situations where you cannot answer or violate the game rules."
        hosting = [
            {"role": "user", "content": prim_prompt},
            {"role": "assistant", "content": "Alright, I understand that my role is to be the host of the Lateral Thinking Puzzle and help users guess the truth by answering their questions. I have fully grasped all the information regarding the story and the truth and have carefully read all the rules. I assure that I will abide by all the rules throughout the game process."},
            {"role": "user", "content": "Please summarize the key points of the story to ensure that you have understood it."},
            {"role": "assistant", "content": story_key},
            {"role": "user", "content": "Please summarize the key points of the truth to ensure that you have understood it."},
            {"role": "assistant", "content": answer_key},
            {"role": "user", "content": "Please restate the rules to ensure that you have understood all of them."},
            {"role": "assistant", "content": rules},
            {"role": "user", "content": "Alright, we can now start the game. Remember, before each response, you should review the key points of the story, the key points of the truth, and the rules. Answer with \"yes\", \"no\", or \"irrelevant\"."},
            {"role": "assistant", "content": f"Alright, as the host of the game, I will adhere to the above rules and ensure that my responses comply with the rules and the information from the truth. Below is your story: \n{story}\n\nYou can start guessing the content of the truth, and I will answer your questions. Please note that your questions should be answerable with \"yes\", \"no\", or \"irrelevant\"."},
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
            logs.append(f'Round {i+1}: {solver}')
            if 'new story' in solver or 'other story' in solver or 'new game' in solver or 'other game' in solver or 'new question' in solver or 'other question' in solver or 'other round' in solver or 'new round' in solver or 'Great job' in solver or 'further question' in solver:
                abort += 2
                host = 'Please continue guessing the truth based on the story and ask a question that can be answered with "yes", "no", or "irrelevant".'
                logs.append(host)
                if abort >= 5:
                    break
                continue

            llm = True
            for key in story_key:
                key = key.strip()
                if key == '':
                    continue
                if key[1] == '.' or key[2] == '.' or key[0] == '-':
                    key = ' '.join(key.split(' ')[1:])
                bleu = sentence_bleu([key], solver.replace('?', '.'), weights=(1, 0, 0, 0))
                if bleu > 0.85:
                    host = 'This Information is already in the story, please ask a new question.'
                    llm = False
                    break
            if llm:
                for key in history:
                    key = key.strip()
                    if key == '':
                        continue
                    bleu = sentence_bleu([key], solver.replace('?', '.'), weights=(1, 0, 0, 0))
                    if bleu > 1:
                        host = 'This is a question that has already been asked. Please ask a new question.'
                        llm = False
                        abort += 1
                        break
            if abort >= 5:
                break

            if llm:
                history.append(solver.replace('?', '.'))
                hosting = hosting[:10]
                if len(known) > 0:
                    hosting += [{"role": 'user', "content": f"{' '.join(known)}\nPlease answer with \"yes\", \"no\", or \"irrelevant\"."}, {"role": "assistant", "content": 'Yes.'}, {"role": 'user', "content": f"{solver}\nPlease answer with \"yes\", \"no\", or \"irrelevant\"."}]
                else:
                    hosting += [{"role": 'user', "content": f"{solver}\nPlease answer with \"yes\", \"no\", or \"irrelevant\"."}]
                host = self.eval_agent.inference(hosting).strip()
                if 'new story' in solver or 'other story' in solver or 'new game' in solver or 'other game' in solver or 'new question' in solver or 'other question' in solver or 'other round' in solver or 'new round' in solver or 'Great job' in solver or 'further question' in solver:
                    abort += 2
                    logs.append(host)
                    if abort >= 5:
                        break
                    continue
                relevant = False
                if host.startswith("Yes") or host.startswith("yes"):
                    correct += 1
                    summary = self.eval_agent.inference([{"role": "user", "content": f"Please restate the following content as a declarative sentence and simplify it into one sentence:\n{solver}"}]).strip()
                    relevant = True
                elif host.startswith("No") or host.startswith("no"):
                    summary = self.eval_agent.inference([{"role": "user", "content": f"Please restate the following content as a declarative sentence by using the opposite meaning and then simplify it into one sentence:\n{solver}"}]).strip()
                    relevant = True
                if relevant:
                    relevance += 1
                    history.append(summary)
                    known.append(summary)
                    reasoning.append(summary)
                    if len(reasoning) >= 2:
                        merge = self.eval_agent.inference([{"role": "user", "content": f"Please simplify the following content into one sentence:\n{' '.join(reasoning)}"}]).strip()
                    else:
                        merge = summary
                    for key in answer_key:
                        key = key.strip()
                        if key == '':
                            continue
                        if key[1] == '.' or key[2] == '.' or key[0] == '-':
                            key1 = ' '.join(key.split(' ')[1:])
                        else:
                            key1 = key
                        if len(solver.replace('?', '')) < len(key1):
                            continue
                        comp_msg = [{"role": "user", "content": f"Please compare the information between Sentence 1 and Sentence 2 to determine if Sentence 2 contains all the information in Sentence 1, including key details and descriptions. Please answer with \"yes\" or \"no\".\nSentence 1: {key1}\nSentence 2: {merge}"}]
                        compare = self.eval_agent.inference(comp_msg).strip()
                        if compare.startswith('Yes') or compare.startswith('yes'):
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