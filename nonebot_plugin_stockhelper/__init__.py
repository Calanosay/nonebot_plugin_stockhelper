from datetime import date
from nonebot.plugin import on_command,on_regex,on_command
from nonebot.adapters.onebot.v11 import Bot, Event
from nonebot.adapters.onebot.v11.message import Message
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER
import asyncio
import efinance as ef
import time
import re

__usage__ = "给机器人发送'看 股票名'即可看股票实时估值,发送'关注'或'监控'或'jk'可令机器人为你持续关注某一股票。监控功能后面还能加上 通知波幅阈值，此值默认0.3，监控时后面不跟数字即为此值。若股票距离上次的涨跌幅超过该值，机器人会通知你。例：'关注 贵州茅台 0.5'，'监控 贵州茅台'，'监控 600519 0.7'。支持部分基金、全球股市。"
__help__plugin_name__ = "看盘小助手"

is_doing = {}
flag = set()

#
def is_num(s):  # 判断是否为数字
    # 去除字符串两边的空格
    s = s.strip()
    flag = True
    # 判断是否是整数
    intRet = re.match("^[0-9]+$", s)
    # 判断是否是小数
    decRet = re.match("^\d+\.\d+$", s)
    # 如果是整数
    if intRet:
        if len(s) > 1 and s[0] == "0":
            # 如果整数的长度大于1，那么判断其首位是否为0，如果为零返回false
            flag = False
            return flag
    elif decRet:
        pos = s.index(".")
        if pos != 1 and s[0] == "0":
            flag = False
            return flag
    else:
        flag = False
        return flag
    return flag


gpjk = on_command('监控', aliases={'关注', 'jk'}, priority=10, rule=to_me())
show = on_command('看股票', aliases={'kgp'}, priority=10, rule=to_me())
stop = on_command("stop", priority=10, rule=to_me())
clear = on_command("清空", permission=SUPERUSER)


@clear.handle()
async def clear_handler(bot: Bot, event: Event):
    is_doing = {}
    flag = set()
    await clear.finish("清空股票功能成功")


def get_now_price(name: str):  # 某个股票当前的价格
    resp = ef.stock.get_quote_history(name, klt=1)['收盘']
    l = len(resp)
    if l == 0:
        return ef.stock.get_quote_history(name, klt=1)['开盘'][0]
    return resp[l - 1]


@show.handle()
async def show_handle(bot: Bot, event: Event):
    temp = str(event.get_message())[len('看股票'):].split()
    call_name = temp[0].strip()
    resp = ef.stock.get_quote_history('gzmt')
    try:
        resp = ef.stock.get_quote_history(call_name, klt=1)
    except:
        await show.finish(message=Message("您输入的股票代码有误~"))
    if resp.empty:
        text = event.get_plaintext()
        if '图' in text or '妹' in text or '女' in text or 'mm' in text or 'setu' in text:
            await show.finish(message=Message("未找到该股票"))
        await show.finish(message=Message("未查到该股票相关信息!"))
    name = resp['股票名称'][0]
    name = name.replace(' ', '')
    now = get_now_price(name)
    yesterday = ef.stock.get_quote_history(name)['收盘']
    l = len(yesterday)
    yesterday = yesterday[l - 2]
    dis = (now - yesterday) / yesterday * 100
    await show.finish(message=Message(f"{name} 当前净值为 {now:.2f} ,当日涨跌幅为 {dis:+.2f} % 哦~"))


@gpjk.handle()  # 股票监控
async def gpjk_handle(bot: Bot, event: Event):
    bound = 0.3
    temp = str(event.get_message())[len('监控'):].split()
    if len(temp) > 1:
        temp[1].strip()
        if is_num(temp[1]): bound = float(temp[1])
        if bound < 0: await gpjk.finish(message=Message("第三个位置请输入大于等于0的数~"))
    call_name = temp[0].strip()
    resp = ef.stock.get_quote_history('gzmt')
    try:
        resp = ef.stock.get_quote_history(call_name, klt=1)
    except:
        await gpjk.finish(message=Message("您输入的股票代码有误~"))
    if resp.empty:
        await gpjk.finish(message=Message("未查到该股票相关信息!"))
    name = resp['股票名称'][0]
    User_id = str(event.get_user_id())

    flag.add(User_id)

    if (name, User_id) not in is_doing.keys():
        is_doing[(name, User_id)] = 1
    else:
        await gpjk.finish(message=Message(f"您已经在监控 {name} 了哦~"))
    res = resp['开盘']
    yesterday = ef.stock.get_quote_history(name)['收盘']
    l = len(yesterday)
    yesterday = yesterday[l - 2]
    pre = get_now_price(name)
    dis = (pre - yesterday) / yesterday * 100
    await gpjk.send(
        message=Message(
            f"开始股票监控，{name} 当前净值为 {pre:.2f} ，涨跌幅为 {dis:+.2f}%，若变化超过 {bound:.2f} 个点，我会告诉你的~[CQ:face,id=317]"))
    pre = dis  # 代表上次更新的涨跌幅
    prel = -1  # 上次更新时的长度
    change_time = 5  # 睡眠的时间
    cnt = 0
    while True:
        await asyncio.sleep(change_time)
        res = ef.stock.get_quote_history(name, klt=1)['收盘']
        if len(res) == 0: res = ef.stock.get_quote_history(name, klt=1)['开盘']
        l = len(res) - 1
        if l == prel:
            cnt += change_time
        else:
            cnt = 0
            prel = l
        if cnt > 80:  # 如果80秒没更新了
            del is_doing[(name, User_id)]
            await gpjk.finish(f"y老师智能检测到当前不在交易时段，本次对 {name} 的监控结束!")
        if User_id not in flag:
            del is_doing[(name, User_id)]
            await gpjk.finish()
        now = res[l]  # 当前价格
        dis = (now - yesterday) / yesterday * 100  # 当前涨跌幅
        # pre代表上次更新时的价值
        if abs(dis - pre) > bound:
            if dis > pre:
                if dis >= 4:
                    await gpjk.send(
                        message=Message(f'【涨】{name} 净值现为 {now:.2f}，涨跌幅为 {dis:+.2f}%，虎年吃大肉！[CQ:face,id=320]'))
                elif dis >= 0:
                    await gpjk.send(message=Message(f'【涨】{name} 净值现为 {now:.2f}，涨跌幅为 {dis:+.2f}%，较上次更新上涨，步步高升！'))
                else:
                    await gpjk.send(message=Message(f'【涨】{name} 净值现为 {now:.2f}，涨跌幅为 {dis:+.2f}%，较上次更新上涨，拨云见日！'))
            else:
                if dis >= 0:
                    await gpjk.send(message=Message(f'【跌】{name} 净值现为 {now:.2f}，涨跌幅为 {dis:+.2f}%，较上次更新下跌，再接再厉！'))
                else:
                    await gpjk.send(message=Message(f'【跌】{name} 净值现为 {now:.2f}，涨跌幅为 {dis:+.2f}%，较上次更新下跌，来日方长！'))
            pre = dis


@stop.handle()
async def stop_handler(bot: Bot, event: Event):  # 清除所有看盘的股票
    User_id = str(event.get_user_id())
    if User_id not in flag:
        await stop.finish(message=Message("您当前没有在看盘哦[CQ:face,id=307]"))
    else:
        flag.remove(User_id)
        await stop.finish(message=Message("您已停止看盘[CQ:face,id=307]"))