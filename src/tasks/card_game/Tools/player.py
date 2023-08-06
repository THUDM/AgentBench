import json

fish_info = [['射水鱼', 'AOE'], ['喷火鱼', '伤害队友'], ['电鳗', 'AOE'], ['翻车鱼', '伤害队友'], ['海狼鱼', '暴击'], ['蝠鲼', '减伤增益'],
             ['海龟', '治疗增益'], ['章鱼', '减伤增益'], ['大白鲨', '暴击最弱敌方'], ['锤头鲨', '暴击最弱敌方'], ['小丑鱼', '承伤增益'], ['拟态鱼', '主动技能']]


def fish_map(fish_id):
    return fish_info[fish_id - 1]


class Fish:
    def __init__(self, fish_json):
        self.player = fish_json['player']
        self.id = fish_json['id']
        self.imitate = fish_json['imitate'] if self.id == 12 else -1
        self.hp = fish_json['hp']
        self.atk = fish_json['atk']
        self.exposed = fish_json['is_expose']


class Player:
    def __init__(self):
        while True:
            print('请输入回放文件路径：', end='')
            path = input()
            if path[-5:] != '.json':
                print('路径输入有误，请重试！')
                continue
            try:
                self.data = json.load(open(path))
                break
            except FileNotFoundError:
                print('路径输入有误，请重试！')

        # 一个列表，元素为两个列表(代表双方**场上**Fish)
        self.field = [[], []]

    def play(self):
        f = open('replay.txt', 'w', encoding='utf-8')
        score_0 = 0
        for turn in self.data:
            if turn is None:
                break
            # 处理异常
            try:
                errors = turn['errors']
                f.write('出错了！(＃°Д°)请查看错误详情：\n')
                for error in errors:
                    if error['type'] == 0:  # 'judger_error'
                        f.write('在{}号玩家的回合中Judger出现错误，请联系开发组成员！\n'.format(error['player']))  # to do
                    elif error['type'] == 1:  # 'parse_failure'
                        f.write('解析{}号玩家的消息失败！\n'.format(error['player']))
                    elif error['type'] == 2:  # 'player_re'
                        f.write('{}号玩家的逻辑发生运行错误！\n'.format(error['player']))
                    elif error['type'] == 3:  # 'player_tle'
                        f.write('{}号玩家超时了！\n'.format(error['player']))
                    elif error['type'] == 4:  # 'type_error'
                        f.write('{}号玩家发送信息中某些key对应value类型非法！\n'.format(error['player']))
                    elif error['type'] == 5:  # 'key_missing'
                        f.write('{}号玩家发送信息中少了某些key！\n'.format(error['player']))
                    elif error['type'] == 6:  # 'value_error'
                        f.write('{}号玩家发送信息中的Action对应值错误！\n'.format(error['player']))
                    elif error['type'] == 7:  # 'range_error'
                        f.write('{}号玩家发送信息中有整数超出范围！\n'.format(error['player']))
                    elif error['type'] == 8:  # 'choice_repeat'
                        f.write('{}号玩家发送信息中的列表内含重复元素！\n'.format(error['player']))
                    elif error['type'] == 9:  # 'repeat_finish'
                        f.write('{}号玩家在选择阶段发送了多次finish信息！\n'.format(error['player']))
                    elif error['type'] == 10:  # 'pick_number_error'
                        f.write('{}号玩家在选择阶段选鱼数量不是4条！\n'.format(error['player']))
                    elif error['type'] == 11:  # 'pick_dead_fish'
                        f.write('{}号玩家试图让某条已上过场的鱼再次上场！\n'.format(error['player']))
                    elif error['type'] == 12:  # 'assert_dead_fish'
                        f.write('{}号玩家试图断言一条被击败的鱼！\n'.format(error['player']))
                    elif error['type'] == 13:  # 'assert_exposed_fish'
                        f.write('{}号玩家试图断言一条已被暴露的鱼！\n'.format(error['player']))
                    elif error['type'] == 14:  # 'action_with_dead_fish'
                        f.write('{}号玩家在行动回合中惊动了已被击败的鱼！\n'.format(error['player']))
                    elif error['type'] == 15:  # 'action_rules_error'
                        # f.write('{}号玩家在行动回合中有非法操作\n'.format(error['player']))
                        if error['action_rules_error_type'] == 1:
                            f.write('{}号玩家试图用【{}】对友方使用技能【{}】，但该技能不能对友方目标使用！\n'.format(error['player'],
                                                                                      fish_map(error['actionfish'])[0],
                                                                                      fish_map(error['actionfish'])[1]))
                        elif error['action_rules_error_type'] == 2:
                            f.write('{}号玩家用【{}】使用技能【{}】时未选择友方目标，但该技能需要对友方目标使用！\n'.format(error['player'],
                                                                                         fish_map(error['actionfish'])[
                                                                                             0],
                                                                                         fish_map(error['actionfish'])[
                                                                                             1]))
                        elif error['action_rules_error_type'] == 3:
                            f.write('{}号玩家试图用【{}】对敌方使用技能【{}】，但该技能不能对敌方目标发动！\n'.format(error['player'],
                                                                                      fish_map(error['actionfish'])[0],
                                                                                      fish_map(error['actionfish'])[1]))
                        elif error['action_rules_error_type'] == 4:
                            f.write('{}号玩家用【{}】使用技能【{}】时未选择敌方目标，但该技能需要对敌方目标使用！\n'.format(error['player'],
                                                                                         fish_map(error['actionfish'])[
                                                                                             0],
                                                                                         fish_map(error['actionfish'])[
                                                                                             1]))
                        elif error['action_rules_error_type'] == 5:
                            f.write('{}号玩家用【{}】使用技能【{}】时指定了多个友方目标，但该技能只能对单个友方发动！\n'.format(error['player'], fish_map(
                                error['actionfish'])[0], fish_map(error['actionfish'])[1]))
                        elif error['action_rules_error_type'] == 6:
                            f.write('{}号玩家用【{}】使用技能【{}】时指定了多个敌方目标，但该技能只能对单个敌方发动！\n'.format(error['player'], fish_map(
                                error['actionfish'])[0], fish_map(error['actionfish'])[1]))
                        elif error['action_rules_error_type'] == 7:
                            f.write('{}号玩家试图用【{}】使用技能【{}】伤害自己，但该技能只能对其他友方发动！\n'.format(error['player'],
                                                                                       fish_map(error['actionfish'])[0],
                                                                                       fish_map(error['actionfish'])[
                                                                                           1]))
                        elif error['action_rules_error_type'] == 8:
                            f.write('{}号玩家试图用【{}】使用技能【{}】为自己施加增益，但该技能只能对其他友方发动！\n'.format(error['player'],
                                                                                          fish_map(error['actionfish'])[
                                                                                              0],
                                                                                          fish_map(error['actionfish'])[
                                                                                              1]))
                        elif error['action_rules_error_type'] == 9:
                            f.write('{}号玩家试图用【{}】对敌方使用技能【{}】，但该技能只能对生命值最低敌方发动！\n'.format(error['player'],
                                                                                         fish_map(error['actionfish'])[
                                                                                             0],
                                                                                         fish_map(error['actionfish'])[
                                                                                             1]))
                break
            except KeyError:
                pass

            try:
                op = turn['operation'][0]
            except KeyError:
                pass
            f.write('操作数：{}  比分：{}:{}\n'.format(turn['state'], int((turn['rounds'] + turn['score']) / 2),
                                                int((turn['rounds'] - turn['score']) / 2)))
            try:
                f.write('行动者：{}\n'.format(op['ID']))
            except KeyError:
                pass

            if turn['gamestate'] == 2:
                # 单轮开始，选鱼
                choice = op['Fish']
                f.write('{}号玩家选择：\n'.format(turn['cur_turn']))
                for fish in choice:
                    f.write('【{}】 {}号位置\n'.format(fish_map(fish['id'])[0] if fish['id'] != 12 else fish_map(fish['id'])[0] + '/' + fish_map(fish['imitate'])[0], fish['pos']))
                f.write('\n\n\n')
                continue
            # 更新鱼信息
            self.field = [[], []]
            if turn['players'][0]['id'] == 0:
                for fish_0 in turn['players'][0]['fight_fish']:
                    self.field[0].append(Fish(fish_0))
                for fish_1 in turn['players'][1]['fight_fish']:
                    self.field[1].append(Fish(fish_1))
            else:
                for fish_0 in turn['players'][0]['fight_fish']:
                    self.field[1].append(Fish(fish_0))
                for fish_1 in turn['players'][1]['fight_fish']:
                    self.field[0].append(Fish(fish_1))
            # 将双方鱼信息写入文件
            pos = 0
            f.write('0号玩家场上信息：\n')
            for x in self.field[0]:
                state = '暴露' if x.exposed else '隐藏'
                f.write(
                    '{}号位置 名称:【{}】 生命值:{} 攻击力:{} {}\n'.format(pos, fish_map(x.id)[0], x.hp, x.atk, state))
                pos += 1
            pos = 0
            f.write('1号玩家场上信息：\n')
            for x in self.field[1]:
                state = '暴露' if x.exposed else '隐藏'
                f.write(
                    '{}号位置 名称:【{}】 生命值:{} 攻击力:{} {}\n'.format(pos, fish_map(x.id)[0], x.hp, x.atk, state))
                pos += 1
            f.write('\n')

            if turn['gamestate'] == 4:
                actions = {}
                num_actions = 0
                info = op['ActionInfo']
                if op['Type'] == 0:  # 平A
                    f.write('{}号玩家第{}位置的【{}】【平A】了{}号玩家第{}位置的【{}】\n'.format(op['ID'], op['MyPos'], fish_map(
                        self.field[op['ID']][op['MyPos']].id)[0], 1 - op['ID'], op['EnemyPos'], fish_map(
                        self.field[1 - op['ID']][op['EnemyPos']].id)[0]))
                elif op['Type'] == 1:  # 主动
                    if info['skill']['type'] == 'crit':
                        f.write('{}号玩家第{}位置的【{}】对{}号玩家第{}位置的【{}】使用了【暴击】！\n'.format(op['ID'], op['MyPos'], fish_map(
                            self.field[op['ID']][op['MyPos']].id)[0], 1 - op['ID'], op['EnemyList'][0], fish_map(
                            self.field[1 - op['ID']][op['EnemyList'][0]].id)[0]))
                    elif info['skill']['type'] == 'subtle':
                        f.write('{}号玩家第{}位置的【{}】对{}号玩家第{}位置的【{}】施加了【增益】\n'.format(op['ID'], op['MyPos'], fish_map(
                            self.field[op['ID']][op['MyPos']].id)[0], op['ID'], op['MyList'][0], fish_map(
                            self.field[op['ID']][op['MyList'][0]].id)[0]))
                    elif info['skill']['type'] == 'infight':
                        f.write('{}号玩家第{}位置的【{}】伤害了【友军】第{}位置的【{}】，获得属性提升\n'.format(op['ID'], op['MyPos'], fish_map(
                            self.field[op['ID']][op['MyPos']].id)[0], op['ID'], fish_map(
                            self.field[op['ID']][op['MyList'][0]].id)[0]))
                    elif info['skill']['type'] == 'aoe':
                        f.write('{}号玩家第{}位置的【{}】对{}号玩家的{}使用了【群体攻击】\n'.format(op['ID'], op['MyPos'], fish_map(
                            self.field[op['ID']][op['MyPos']].id)[0], 1 - op['ID'], '【' + '】，【'.join(
                            [fish_map(self.field[1 - op['ID']][enemy].id)[0] for enemy in op['EnemyList']]) + '】'))
                # f.write('本回合触发被动技能：\n')
                try:
                    for passive in info['passive']:
                        num_actions = max(num_actions, passive['time'])
                        if passive['type'] == 'counter':
                            actions[passive['time']] = '被动：' + '{}号玩家第{}位置【{}】的【反伤】被触发\n'.format(passive['player'],
                                                                                                 passive['source'],
                                                                                                 fish_map(
                                                                                                     self.field[passive[
                                                                                                         'player']][
                                                                                                         passive[
                                                                                                             'source']].id)[
                                                                                                     0])
                        elif passive['type'] == 'heal':
                            actions[passive['time']] = '被动：' + '{}号玩家第{}位置【{}】的【治疗】被触发\n'.format(passive['player'],
                                                                                                 passive['source'],
                                                                                                 fish_map(
                                                                                                     self.field[passive[
                                                                                                         'player']][
                                                                                                         passive[
                                                                                                             'source']].id)[
                                                                                                     0])
                        elif passive['type'] == 'explode':
                            actions[passive['time']] = '被动：' + '{}号玩家第{}位置【{}】的【爆炸】被触发\n'.format(passive['player'],
                                                                                                 passive['source'],
                                                                                                 fish_map(
                                                                                                     self.field[passive[
                                                                                                         'player']][
                                                                                                         passive[
                                                                                                             'source']].id)[
                                                                                                     0])
                        elif passive['type'] == 'deflect':
                            actions[passive['time']] = '被动：' + '{}号玩家第{}位置【{}】的【承伤】被触发\n'.format(passive['player'],
                                                                                                 passive['source'],
                                                                                                 fish_map(
                                                                                                     self.field[passive[
                                                                                                         'player']][
                                                                                                         passive[
                                                                                                             'source']].id)[
                                                                                                     0])
                        elif passive['type'] == 'reduce':
                            actions[passive['time']] = '被动：' + '{}号玩家第{}位置【{}】的【减伤】被触发，实际伤害与原伤害比例为{}\n'.format(
                                passive['player'], passive['source'],
                                fish_map(self.field[passive['player']][
                                             passive['source']].id)[0],
                                passive['value'])
                except KeyError:
                    pass
                    # f.write('本回合无被动技能触发\n')

                # f.write('本回合受伤记录：\n')
                try:
                    for hit in info['hit']:
                        num_actions = max(num_actions, hit['time'])
                        hit_type = '直接攻击' if hit['traceable'] else '伤害'
                        actions[hit['time']] = '伤害：' + '{}号玩家第{}位置的【{}】受到{}【{}】\n'.format(hit['player'], hit['target'],
                                                                                          fish_map(
                                                                                              self.field[hit['player']][
                                                                                                  hit['target']].id)[0],
                                                                                          hit['value'], hit_type)
                except KeyError:
                    pass
                    # f.write('本回合无受伤\n')

                # 输出action
                if num_actions > 0:
                    f.write('\n行为记录：\n')
                    for i in range(num_actions):
                        f.write('(' + str(i + 1) + ')' + actions[i + 1])
            elif op['Action'] == 'Assert':
                f.write(
                    '{}号玩家进行了断言，ta断言对方{}位置的鱼为【{}】，'.format(op['ID'], op['Pos'], fish_map(int(op['id']))[0]))
                f.write('断言成功了！ψ(｀∇´)ψ\n') if self.field[1 - op['ID']][int(op['Pos'])].id == int(op['id']) else f.write(
                    '断言失败了！(っ °Д °;)っ\n')
            elif op['Action'] == 'Null':
                f.write('{}号玩家放弃了断言！\n'.format(op['ID']))

            if turn['gamestate'] == 0:
                if turn['over']:
                    f.write('游戏结束，{}号玩家获胜！ヾ(≧▽≦*)o'.format(int(0.5 - turn['score'] / abs(turn['score']) * 0.5)))
                else:
                    f.write(
                        '第{}轮结束，{}号玩家此轮胜利！q(≧▽≦q)\n\n\n'.format(turn['rounds'], 0 if turn['score'] > score_0 else 1))
                    score_0 = turn['score']
            f.write('\n\n\n')
        f.close()


if __name__ == '__main__':
    player = Player()
    player.play()
