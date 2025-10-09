from .interaction import Database

class DBResultProcessor:
    """
    处理数据库查询结果和比较的类
    只对外暴露compare_results和calculate_tables_hash接口
    """
    
    @staticmethod
    def compare_results(answer, ground_truth, query_type):
        """
        比较答案和标准答案
        
        参数:
        answer - 模型输出的答案
        ground_truth - 标准答案
        query_type - 查询类型 (SELECT/INSERT/UPDATE/DELETE)
        
        返回:
        bool - 答案是否匹配
        """
        try:
            # 处理answer和ground_truth
            processed_answer = DBResultProcessor._clean_answer(answer)
            processed_ground_truth = DBResultProcessor._clean_answer(ground_truth)
            
            if query_type in ("INSERT", "DELETE", "UPDATE"):
                return processed_answer == processed_ground_truth
                
            # 打印处理后的结果用于调试
            print("Processed answer:", processed_answer)
            print("Processed ground_truth:", processed_ground_truth)
            
            # 比较逻辑
            if len(processed_answer) == 1 and len(processed_ground_truth) == 1:
                # 获取处理后的值
                ans_val = processed_answer[0]
                gt_val = processed_ground_truth[0]
                
                # 如果两个值都是特殊值（0、undefined等），认为它们相等
                if ans_val == "0" and gt_val == "0":
                    return True
                    
                # 浮点数比较
                if DBResultProcessor._is_float(ans_val) and DBResultProcessor._is_float(gt_val):
                    return DBResultProcessor._float_equal(ans_val, gt_val)

                # 字符串比较
                return ans_val == gt_val
            else:
                # 如果都是浮点数，执行浮点比较
                if (all(DBResultProcessor._is_float(x) for x in processed_answer) and 
                    all(DBResultProcessor._is_float(x) for x in processed_ground_truth)):
                    # 检查每个答案是否都有匹配的标准答案（考虑精度）
                    if len(processed_answer) != len(processed_ground_truth):
                        return False
                        
                    # 创建匹配标记
                    matched_gt = [False] * len(processed_ground_truth)
                    
                    for ans in processed_answer:
                        matched = False
                        for i, gt in enumerate(processed_ground_truth):
                            if not matched_gt[i] and DBResultProcessor._float_equal(ans, gt):
                                matched_gt[i] = True
                                matched = True
                                break
                        if not matched:
                            return False
                            
                    return all(matched_gt)
                
                # 普通比较（使用集合）
                return set(processed_answer) == set(processed_ground_truth)
                    
        except Exception as e:
            print(f"Comparison error: {e}")
            return False
    
    @staticmethod
    async def calculate_tables_hash_async(database: Database, entry):
        """异步计算所有表的组合哈希值"""
        # 获取表信息（可能是单个表或表列表）
        tables = entry["table"] if isinstance(entry["table"], list) else [entry["table"]]
        
        # 收集所有表的哈希值
        table_hashes = []
        for table in tables:
            table_name = table["table_name"]
            table_info = table["table_info"]
            table_hash = await DBResultProcessor._get_table_hash_async(database, table_info, table_name)
            # 提取哈希值
            cleaned_hash = table_hash.strip("[]()")
            hash_value = cleaned_hash.split(",")[0].strip().strip("'")
            table_hashes.append(hash_value)
        
        # 将所有哈希值排序并组合
        combined_hash = "_".join(sorted(table_hashes))
        return combined_hash
    
    @staticmethod
    async def _get_table_hash_async(database: Database, table_info, table_name):
        """异步获取单个表的MD5哈希值"""
        columns = ",".join(
            [f"`{column['name']}`" for column in table_info["columns"]]
        )
        md5_query = (
            f"select md5(group_concat(rowhash order by rowhash)) as hash "
            f"from( SELECT substring(MD5(CONCAT_WS(',', {columns})), 1, 5) AS rowhash "
            f"FROM `{table_name}`) as sub;"
        )
        return await database.execute(md5_query)
    
    @staticmethod
    def _normalize_special_values(value):
        """处理特殊值、百分比和格式化数字"""
        if value is None:
            return "0"  # 将 None 转换为 "0"
        
        # 转换为字符串
        str_value = str(value).strip()
        
        # 处理百分比
        if str_value.endswith('%'):
            try:
                # 去掉百分号，转为数值
                return str_value[:-1].strip()
            except:
                pass
        
        # 处理千位分隔符
        if ',' in str_value and not str_value.startswith('[') and not str_value.endswith(']'):
            try:
                # 去掉逗号
                str_value = str_value.replace(',', '')
            except:
                pass
        
        # 转换为小写进行特殊值比较
        lower_value = str_value.lower()
        
        # 处理特殊值映射
        special_values_map = {
            "none": "0",
            "null": "0",
            "undefined": "0",
            "nan": "0",
            "inf": "0",
            "infinity": "0",
            "-inf": "0",
            "-infinity": "0",
            "": "0",  # 空字符串
        }
        
        return special_values_map.get(lower_value, str_value)
    
    @staticmethod
    def _clean_mysql_result(result):
        """处理MySQL执行结果的特殊格式 [(value,)] 或多元组情况 [(value1,), (value2,), ...]"""
        if isinstance(result, str) and result.startswith("[") and result.endswith("]"):
            try:
                # 尝试使用 eval 安全解析
                parsed_result = eval(result)
                
                # 检查是否是元组列表
                if isinstance(parsed_result, list) and all(isinstance(item, tuple) for item in parsed_result):
                    # 处理每个元组
                    cleaned_values = []
                    for item in parsed_result:
                        # 对于单值元组 (value,)
                        if len(item) == 1:
                            value = str(item[0]).strip().strip("'\"")
                            cleaned_values.append(value)
                        # 也可以添加对多值元组的处理逻辑，但根据您的需求似乎只需要处理单值元组
                    
                    return cleaned_values
            except:
                # 如果 eval 失败，继续尝试原来的方法
                pass
                
            # 原来的方法 - 用于单个元组情况
            try:
                # 处理类似 "[(293.0,)]" 的格式
                result_stripped = result.strip("[]")
                # 检查是否只有一个元组
                if result_stripped.count("(") == 1 and result_stripped.startswith("(") and result_stripped.endswith(",)"):
                    # 提取括号中的值
                    value = result_stripped[1:-2]  # 移除 ( 和 ,)
                    # 去除可能存在的引号
                    value = value.strip().strip("'\"")
                    return [value]
            except:
                pass
        return None
    
    
    @staticmethod
    def _clean_answer(answer):
        """清理和标准化答案"""
        # 处理 None 值
        if answer is None:
            return ["0"]
            
        # 首先检查是否是MySQL结果格式
        mysql_result = DBResultProcessor._clean_mysql_result(answer)
        if mysql_result is not None:
            return [DBResultProcessor._normalize_special_values(x) for x in mysql_result]

        if isinstance(answer, str):
            # 移除多余的空格
            answer = answer.strip()
            # 如果是字符串形式的列表
            if answer.startswith("[") and answer.endswith("]"):
                try:
                    # 先尝试用eval转换
                    cleaned = eval(answer)
                    if isinstance(cleaned, list):
                        # 处理可能的元组结果
                        result = []
                        for item in cleaned:
                            if isinstance(item, tuple) and len(item) == 1:
                                # 处理元组的情况 (value,)
                                value = str(item[0]).strip().strip("'\"")
                                result.append(DBResultProcessor._normalize_special_values(value))
                            else:
                                value = str(item).strip().strip("'\"")
                                result.append(DBResultProcessor._normalize_special_values(value))
                        return result
                except:
                    # 如果eval失败，手动处理
                    answer = answer[1:-1]
                    items = []
                    current = ""
                    in_quotes = False
                    for char in answer:
                        if char in '"\'':
                            in_quotes = not in_quotes
                        elif char == ',' and not in_quotes:
                            if current:
                                items.append(DBResultProcessor._normalize_special_values(current.strip().strip("'\"")))
                                current = ""
                        else:
                            current += char
                    if current:
                        items.append(DBResultProcessor._normalize_special_values(current.strip().strip("'\"")))
                    return items
            else:
                # 单个值
                return [DBResultProcessor._normalize_special_values(answer.strip().strip("'\""))]
        elif isinstance(answer, (list, tuple)):
            # 处理列表或元组
            result = []
            for item in answer:
                if isinstance(item, tuple) and len(item) == 1:
                    # 处理元组的情况 (value,)
                    value = str(item[0]).strip().strip("'\"")
                    result.append(DBResultProcessor._normalize_special_values(value))
                else:
                    value = str(item).strip().strip("'\"")
                    result.append(DBResultProcessor._normalize_special_values(value))
            return result
        else:
            return [DBResultProcessor._normalize_special_values(str(answer).strip().strip("'\""))]
    
    @staticmethod
    def _is_float(value):
        """检查是否可以转换为浮点数"""
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def _float_equal(a, b, tol=1e-2):
        """比较两个浮点数是否相等（考虑精度）"""
        try:
            return abs(float(a) - float(b)) <= tol
        except (ValueError, TypeError):
            return False
