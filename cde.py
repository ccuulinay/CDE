import re
import itertools
from datetime import datetime, timedelta
import jieba.posseg as psg
import cn2an
import logging
import pprint

key_day_offset = {
    '前天': -2
    , '昨天': -1
    , '今天': 0
    , '明天': 1
    , '后天': 2
    , '前日': -2
    , '昨日': -1
    , '今日': 0
    , '明日': 1
    , '后日': 2
    , "寻日": -1
    , "听日": 1
}

key_week_offset = {
    '上周': -1
    , '本周': 0
    , '下周': 1
}

datetime_cn_unit_seq = ['年', '月', '日号', "时:.点", "分", "秒"]

datetime_params_seq = ['year', 'month', 'day', 'hour', 'minute', 'second']
datetime_offset_adj = ['pm', "week", "adj_week"]


def get_next_dt_unit(cur_unit):
    for i, u in enumerate(datetime_cn_unit_seq):
        if cur_unit in u:
            return datetime_cn_unit_seq[i + 1][0]
    try:
        _num = cn2an.cn2an(cur_unit, mode="smart")
        if _num > 24:
            return "号"
        else:
            return "时"
    except:
        return "时"


def _jieba_datetime_info_extract(text):
    time_exps = []
    time_exp = ''

    prev_w, prev_f = "", ""

    for w, f in psg.cut(text):
        if w in key_day_offset:
            if time_exp != '':
                time_exps.append(time_exp)
            time_exp = (datetime.today() + timedelta(days=key_day_offset.get(w, 0))).strftime('%Y年%m月%d日')
        else:
            if f in ['m', 't']:
                time_exp = time_exp + w
            elif f in ['uj', 'x']:
                if prev_f in ['m', 't']:
                    try:
                        _ = cn2an.cn2an(str(prev_w), mode="smart")
                        if len(time_exp) == len(prev_w):
                            last_unit = prev_w
                        else:
                            last_unit = time_exp[time_exp.index(prev_w) - 1]
                        patch_unit = get_next_dt_unit(last_unit)
                        time_exp = time_exp + patch_unit
                    except Exception as e:
                        # print(e)
                        pass

            else:
                if time_exp:
                    time_exps.append(time_exp)
                    time_exp = ''
        prev_w = w
        prev_f = f
    if time_exp != '':
        time_exps.append(time_exp)
    return time_exps


def text_to_datetime_info(exp):
    if exp is None or len(exp) == 0:
        return None

    dt_pattern_dict = {
        "year_pattern": r"[0-9零一二两三四五六七八九十]+年"
        , "month_pattern": r"[0-9一二两三四五六七八九十]+月"
        , "day_pattern": r"[0-9一二两三四五六七八九十]+[号日]"
        , "week_pattern": r"星期[1-7一二三四五六日天]|周[1-7一二三四五六日天]"
        , "pm_pattern": r"上午|中午|下午|早上|晚上|早|晚"
        , "hour_pattern": r"[0-9零一二两三四五六七八九十百]+[点:\.时]"
        , "minute_pattern": r"[0-9零一二三四五六七八九十百]+分"
        , "second_pattern": r"[0-9零一二三四五六七八九十百]+秒"
        , "adj_week_pattern": r"[上本下]+周"
    }

    raw_dt_info = {}
    for k, pattern in dt_pattern_dict.items():
        dt_key = k.replace("_pattern", "_string")
        raw_dt_info[dt_key] = re.findall(pattern, exp, re.S)

    return raw_dt_info


def dt_info_to_dt(dt_info_set, adj_info=None):
    rdt = []

    # Handle basic datetime.
    dt_params = {}

    if len(dt_info_set) != len(datetime_params_seq):
        logging.warning("Input datetime information set is not valid.")
        return []

    for i, d_name in enumerate(datetime_params_seq):
        d_info = dt_info_set[i]
        if d_name in ['hour', 'minute', 'second']:
            if not d_info:
                d_num = "00"
                dt_params[d_name] = int(d_num)
                continue
        if d_info:
            try:
                d_num = cn2an.cn2an(str(d_info[:-1]), mode='smart')
                if d_num:
                    dt_params[d_name] = int(d_num)
            except Exception as e:
                logging.warning(e)
                pass
    dt_obj = datetime.today().replace(**dt_params)

    # Handle adjustment.
    if adj_info:
        # checking pm adjustment:
        pm = adj_info.get("pm_string")
        if pm:
            if (len(pm) == 1) and (pm[0] in ['中午', "下午", "晚上", "晚"]) and (dt_obj.time().hour < 12):
                dt_obj = dt_obj.replace(hour=dt_obj.time().hour + 12)

        # checking week adjustment:
        week = adj_info.get("week_string")
        adj_week = adj_info.get("adj_week_string")
        dt_obj_1 = None

        if adj_week:
            if len(adj_week) == 1:
                adj_week_num = key_week_offset.get(adj_week[0], 0)
            else:
                adj_week_num = 0
        else:
            adj_week_num = 0

        if week:
            if len(week) == 1:
                week_cn = str(week[0][-1])

                if week_cn in ["日", "天"]:
                    week_cn = "7"
                try:
                    week_num = cn2an.cn2an(week_cn, mode='smart')
                    if week_num:
                        # check if current dt object is today
                        if dt_obj.date() == datetime.today().date() and "day" not in dt_params.keys():
                            dt_obj = dt_obj + timedelta(days=(week_num - dt_obj.isoweekday() + 7 * int(adj_week_num)))
                        elif dt_obj.date() == datetime.today().date() and "day" in dt_params.keys():
                            if dt_obj.isoweekday() == week_num:
                                pass
                            else:
                                # print(week_num, dt_obj.isoweekday(), 7*int(adj_week_num))
                                dt_obj_1 = dt_obj + timedelta(
                                    days=(week_num - dt_obj.isoweekday() + 7 * int(adj_week_num)))
                        else:
                            dt_obj_1 = dt_obj + timedelta(days=(week_num - dt_obj.isoweekday() + 7 * int(adj_week_num)))
                except Exception as e:
                    logging.warning(e)
                    pass
        if dt_obj_1:
            rdt.append(dt_obj_1.strftime('%Y-%m-%d %H:%M:%S'))

    rdt.append(dt_obj.strftime('%Y-%m-%d %H:%M:%S'))
    return rdt


def text_to_datetime(exp):
    datetime_info_dict = text_to_datetime_info(exp)

    raw_dt_info = []
    for dinfo in datetime_params_seq:
        # print(dinfo)
        d_key = dinfo + "_string"
        d_value = datetime_info_dict[d_key]
        if d_value:
            raw_dt_info.append(d_value)
        else:
            raw_dt_info.append([""])

    _dt_info = list(itertools.product(*raw_dt_info))

    raw_adj_info = {}
    for adj_info in datetime_offset_adj:
        # print(adj_info)
        d_key = adj_info + "_string"
        d_val = datetime_info_dict[d_key]
        raw_adj_info[d_key] = d_val

    dt_strs = []
    for dt_str in _dt_info:
        _temp_dt_strs = dt_info_to_dt(dt_str, adj_info=raw_adj_info)
        dt_strs.extend(_temp_dt_strs)
    # dt_strs = [*dt_info_to_dt(dt_str) for dt_str in _dt_info]
    return dt_strs


def text_datetime_extractor(text):
    dt_exps = _jieba_datetime_info_extract(text)

    dt_entity = {}
    for exp in dt_exps:
        dt_strs = text_to_datetime(exp)
        dt_entity[exp] = dt_strs

    return {text: dt_entity}


if __name__ == '__main__':

    import sys
    text = sys.argv[1]
    pprint.pprint(text_datetime_extractor(text))

