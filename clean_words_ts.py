#!/usr/bin/env python3
"""
检测并清理 TypeScript 单词文件中 words 和 valid 数组之间的重复单词。
支持格式：
    const words={"words":["cigar","above",...],"valid":["about","aahed",...]};
    export default words;

用法:
    python clean_words_ts.py <文件路径>
"""

import re
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

# 修复 Windows 终端编码，确保 UTF-8 输出
sys.stdout.reconfigure(encoding="utf-8")


# ── ANSI 颜色 ────────────────────────────────────────────────────────────────
class Color:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    DIM    = "\033[2m"

def c(text, *codes):
    return "".join(codes) + str(text) + Color.RESET


# ── 解析文件 ──────────────────────────────────────────────────────────────────
def strip_js_comments(text: str) -> str:
    """移除 JS 单行注释 (// ...)，但保留 URL 中的 //"""
    text = re.sub(r'(?<!:)//.*$', '', text)
    # 移除 ] 或 } 前多余的逗号（JSON 不允许 trailing comma）
    text = re.sub(r',\s*(\])', r'\1', text)
    text = re.sub(r',\s*(\})', r'\1', text)
    return text




def extract_array(content: str, key: str) -> tuple[list, int, int]:
    """从 TS 文件内容中提取指定 key 的数组，返回 (数组内容, 起始偏移, 结束偏移)"""
    # 找 key 对应的数组起始
    pattern = rf'"{key}"\s*:\s*\['
    match = re.search(pattern, content)
    if not match:
        print(c(f"\n错误: 未找到 `{key}` 数组。\n", Color.RED))
        sys.exit(1)

    # 找数组结束的 ]
    start = match.end()  # [ 之后的位置
    depth = 1
    i = start
    while i < len(content):
        if content[i] == '[':
            depth += 1
        elif content[i] == ']':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
        i += 1
    else:
        print(c(f"\n错误: `{key}` 数组未正确闭合。\n", Color.RED))
        sys.exit(1)

    # 提取数组文本并解析
    arr_text = strip_js_comments(content[start - 1:end])
    try:
        arr = json.loads(arr_text)
    except json.JSONDecodeError as e:
        print(c(f"\n错误: `{key}` 数组 JSON 解析失败: {e}\n", Color.RED))
        sys.exit(1)

    return arr, match.start(), end


def rebuild_arrays(content: str, data_start: int, data_end: int,
                   words_range: tuple[int, int], new_words: list,
                   valid_range: tuple[int, int], new_valid: list) -> str:
    """用新数组替换原文件中对应区域，保持其他部分不变（含注释和缩进）"""
    # 用紧凑 JSON 格式生成新数组文本
    words_json = '"words":' + json.dumps(new_words, ensure_ascii=False, separators=(',', ':'))
    valid_json = '"valid":' + json.dumps(new_valid, ensure_ascii=False, separators=(',', ':'))

    result = content
    # 先替换靠后的 valid（这样前面的偏移量不受影响）
    ws, we = words_range
    vs, ve = valid_range
    if ve > we:
        result = result[:vs] + valid_json + result[ve:]
        result = result[:ws] + words_json + result[we:]
    else:
        result = result[:ws] + words_json + result[we:]
        result = result[:vs] + valid_json + result[ve:]

    return result


def show_dupes(label: str, dupes: list, cols: int = 6):
    print(f"\n  {c('⚠ ' + label, Color.RED + Color.BOLD)}: {c(len(dupes), Color.BOLD)} 个\n")
    for i in range(0, len(dupes), cols):
        row = dupes[i:i + cols]
        print("    " + "  ".join(c(f"{w:<10}", Color.YELLOW) for w in row))


def find_self_dupes(lst: list) -> list:
    seen: set = set()
    dupes: set = set()
    for w in lst:
        if w in seen:
            dupes.add(w)
        seen.add(w)
    return sorted(dupes)


def dedup_list(lst: list) -> tuple[list, int]:
    """保序去重，返回 (去重后列表, 删除数量)"""
    seen: set = set()
    result: list = []
    removed = 0
    for w in lst:
        if w in seen:
            removed += 1
        else:
            result.append(w)
            seen.add(w)
    return result, removed


# ── 主流程 ────────────────────────────────────────────────────────────────────
def main():
    # if len(sys.argv) < 2:
    #     print(f"\n用法: {c('python clean_words_ts.py <文件路径>', Color.BOLD)}\n")
    #     sys.exit(1)

    filepath = Path('./src/words_5.ts')
    if not filepath.exists():
        print(c(f"\n错误: 文件不存在: {filepath}\n", Color.RED))
        sys.exit(1)

    print(f"\n{c('═' * 60, Color.CYAN)}")
    print(f"  {c('Wordle 单词列表重复检测工具', Color.BOLD)}")
    print(f"{c('═' * 60, Color.CYAN)}\n")
    print(f"  文件: {c(filepath, Color.BOLD)}")

    content = filepath.read_text(encoding="utf-8")
    words_list, words_start, words_end = extract_array(content, "words")
    valid_list, valid_start, valid_end = extract_array(content, "valid")

    print(f"\n  {c('words', Color.YELLOW)} 数组: {c(len(words_list), Color.BOLD)} 个单词")
    print(f"  {c('valid', Color.YELLOW)} 数组: {c(len(valid_list), Color.BOLD)} 个单词")
    print(f"\n{c('─' * 60, Color.DIM)}")

    # ── 三类检测 ──────────────────────────────────────────────────────────────
    words_self  = find_self_dupes(words_list)
    valid_self  = find_self_dupes(valid_list)
    words_set   = set(words_list)
    cross_dupes = sorted(w for w in set(valid_list) if w in words_set)

    if not words_self and not valid_self and not cross_dupes:
        print(f"\n  {c('✓ 未发现任何重复单词，文件无需修改。', Color.GREEN)}\n")
        sys.exit(0)

    if words_self:
        show_dupes("words 数组内部重复", words_self)
    if cross_dupes:
        show_dupes("valid 与 words 共同出现", cross_dupes)
    if valid_self:
        show_dupes("valid 数组内部重复", valid_self)

    print(f"\n{c('─' * 60, Color.DIM)}\n")
    if words_self:
        print(f"  将从 {c('words', Color.YELLOW)} 中删除重复的 {c(len(words_self), Color.BOLD)} 种单词")
    if cross_dupes or valid_self:
        total_valid_kinds = len(set(cross_dupes) | set(valid_self))
        print(f"  将从 {c('valid', Color.YELLOW)} 中删除重复的 {c(total_valid_kinds, Color.BOLD)} 种单词")
    print()

    answer = input(f"  {c('确认删除？[y/N] >', Color.BOLD)} ").strip().lower()
    if answer not in ("y", "yes"):
        print(f"\n  {c('已取消，文件未修改。', Color.DIM)}\n")
        sys.exit(0)

    # ── 备份 ──────────────────────────────────────────────────────────────────
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = filepath.with_suffix(f".{ts}.bak")
    shutil.copy2(filepath, backup)
    print(f"\n  备份已保存: {c(backup, Color.DIM)}")

    # ── 生成新 words（保序去重）───────────────────────────────────────────────
    words_removed = 0
    if words_self:
        new_words, words_removed = dedup_list(words_list)
        words_set = set(new_words)  # 用去重后的 words_set 做跨数组检查
    else:
        new_words = words_list

    # ── 生成新 valid（去跨数组重复 + 自身去重）───────────────────────────────
    new_valid: list = []
    seen_valid: set = set()
    valid_removed = 0

    for w in valid_list:
        if w in words_set or w in seen_valid:
            valid_removed += 1
        else:
            new_valid.append(w)
            seen_valid.add(w)

    words_range = (words_start, words_end)
    valid_range = (valid_start, valid_end)
    new_content = rebuild_arrays(content, -1, -1, words_range, new_words, valid_range, new_valid)
    filepath.write_text(new_content, encoding="utf-8")

    print(f"\n  {c('✓ 完成！', Color.GREEN + Color.BOLD)}")
    if words_self:
        print(f"  words: {c(len(words_list), Color.BOLD)} → {c(len(new_words), Color.BOLD)} 个（删除 {c(words_removed, Color.BOLD)} 条）")
    print(f"  valid: {c(len(valid_list), Color.BOLD)} → {c(len(new_valid), Color.BOLD)} 个（删除 {c(valid_removed, Color.BOLD)} 条）\n")
    print(f"{c('═' * 60, Color.CYAN)}\n")


if __name__ == "__main__":
    main()
