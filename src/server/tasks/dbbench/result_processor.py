from __future__ import annotations

import ast
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .interaction import Database


class _DecimalLiteral(ast.NodeTransformer):
    """Permit MySQL's Decimal repr without evaluating arbitrary code."""

    def visit_Call(self, node):
        if (not isinstance(node.func, ast.Name) or node.func.id != "Decimal"
                or len(node.args) != 1 or node.keywords):
            raise ValueError("Unsupported expression in a DBBench result")
        value = ast.literal_eval(node.args[0])
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ValueError("Unsupported Decimal argument")
        return ast.copy_location(ast.Constant(value=Decimal(value)), node)


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
                
                # Zero answers only match zero ground truth.
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
            return "<NULL>"
        
        # 转换为字符串
        str_value = str(value).strip()
        
        # 处理百分比
        if str_value.endswith('%'):
            return str_value[:-1].strip()
        
        # 处理千位分隔符
        if ',' in str_value and not str_value.startswith('[') and not str_value.endswith(']'):
            str_value = str_value.replace(',', '')
        
        # 转换为小写进行特殊值比较
        lower_value = str_value.lower()
        
        # 处理特殊值映射
        special_values_map = {
            "none": "<NULL>",
            "null": "<NULL>",
            "undefined": "<UNDEFINED>",
            "nan": "<NAN>",
            "inf": "<POSITIVE_INFINITY>",
            "infinity": "<POSITIVE_INFINITY>",
            "-inf": "<NEGATIVE_INFINITY>",
            "-infinity": "<NEGATIVE_INFINITY>",
            "": "<EMPTY>",
        }
        
        return special_values_map.get(lower_value, str_value)
    
    @staticmethod
    def _parse_result_literal(result):
        if len(result) > 100_000:
            raise ValueError("DBBench result literal is too large")
        tree = ast.parse(result, mode="eval")
        return ast.literal_eval(_DecimalLiteral().visit(tree))

    @staticmethod
    def _format_mysql_row(row):
        if len(row) == 1:
            return DBResultProcessor._normalize_special_values(row[0])
        return repr(row)

    @staticmethod
    def _clean_mysql_result(result):
        """Parse MySQL's list-of-tuples repr, retaining every column."""
        if isinstance(result, str) and result.startswith("[") and result.endswith("]"):
            try:
                parsed_result = DBResultProcessor._parse_result_literal(result)
                if isinstance(parsed_result, list) and all(isinstance(item, tuple) for item in parsed_result):
                    return [DBResultProcessor._format_mysql_row(row) for row in parsed_result]
            except (SyntaxError, ValueError, TypeError, RecursionError, InvalidOperation):
                return None
        return None
    
    
    @staticmethod
    def _clean_answer(answer):
        """清理和标准化答案"""
        # 处理 None 值
        if answer is None:
            return [DBResultProcessor._normalize_special_values(None)]
            
        # 首先检查是否是MySQL结果格式
        mysql_result = DBResultProcessor._clean_mysql_result(answer)
        if mysql_result is not None:
            return mysql_result

        if isinstance(answer, str):
            # 移除多余的空格
            answer = answer.strip()
            # 如果是字符串形式的列表
            if answer.startswith("[") and answer.endswith("]"):
                try:
                    cleaned = DBResultProcessor._parse_result_literal(answer)
                    if isinstance(cleaned, list):
                        return DBResultProcessor._clean_answer(cleaned)
                except (SyntaxError, ValueError, TypeError, RecursionError, InvalidOperation):
                    # An invalid or truncated result must not become an empty match.
                    return [answer]
            else:
                # 单个值
                return [DBResultProcessor._normalize_special_values(answer.strip().strip("'\""))]
        elif isinstance(answer, (list, tuple)):
            # 处理列表或元组
            result = []
            for item in answer:
                if isinstance(item, tuple):
                    result.append(DBResultProcessor._format_mysql_row(item))
                    continue
                if isinstance(item, str):
                    mysql_rows = DBResultProcessor._clean_mysql_result(item)
                    if mysql_rows is not None:
                        result.extend(mysql_rows)
                        continue
                    if item.startswith("(") and item.endswith(")"):
                        try:
                            row = DBResultProcessor._parse_result_literal(item)
                            if isinstance(row, tuple):
                                result.append(DBResultProcessor._format_mysql_row(row))
                                continue
                        except (SyntaxError, ValueError, TypeError, RecursionError, InvalidOperation):
                            pass
                # Keep the existing tolerance for answers such as ["'value'"].
                result.append(DBResultProcessor._normalize_special_values(
                    str(item).strip().strip("'\"")
                ))
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
