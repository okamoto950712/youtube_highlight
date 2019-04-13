import ast
import os
import pprint
import sys

import requests
from bs4 import BeautifulSoup


def get_comment(target_url):
    '''
    list型を返す
    要素はdict型
        message コメント str型
        timestanp 投稿された時間(秒) int型
        purchase スパチャ金額 int型
    '''
    comment_data = []
    dict_str = ''
    next_url = ''
    session = requests.Session()
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36'}

    # 動画ページにrequestsを実行，htmlソースを入手し，live_chat_replayの先頭urlを入手
    try:
        html = requests.get(target_url)
    except:
        print('urlが間違っている?')
        print(sys.exc_info()[0])
        sys.exit()

    soup = BeautifulSoup(html.text, 'html.parser')

    for iframe in soup.find_all('iframe'):
        if 'live_chat_replay' in iframe['src']:
            next_url = iframe['src']

    while True:
        html = session.get(next_url, headers=headers)
        soup = BeautifulSoup(html.text, 'lxml')

        # 次に飛ぶurlのデータがある部分をfind_allで探してsplitで整形
        for scrp in soup.find_all('script'):
            if 'window["ytInitialData"]' in scrp.text:
                dict_str = scrp.text.split(' = ', 1)[1]

        # javascript表記を整形，falseとtrueの表記を直す
        dict_str = dict_str.replace('false', 'False')
        dict_str = dict_str.replace('true', 'True')

        # 辞書形式と認識するとかんたんにデータを取得できるが，末尾に邪魔なのがあるので消しておく（「空白2つ + \n + ;」を消す）
        dict_str = dict_str.rstrip('  \n;')
        # 辞書形式に変換
        try:
            dics = eval(dict_str)
        except:
            with open('error_dict_str.txt', 'w') as f:
                f.write(dict_str)
            with open('error_soup.txt', 'w') as f:
                f.write(str(soup))
            print('コメントの変換に失敗しました')
            # print(dict_str)
            print(sys.exc_info()[0])
            sys.exit()

        # 'https://www.youtube.com/live_chat_replay?continuation=' + continue_url が次のlive_chat_replayのurl
        # 次のurlが取得できなければ終了
        try:
            continue_url = dics['continuationContents']['liveChatContinuation'][
                'continuations'][0]['liveChatReplayContinuationData']['continuation']
        except:
            break
        next_url = 'https://www.youtube.com/live_chat_replay?continuation=' + continue_url

        # dics['continuationContents']['liveChatContinuation']['actions']がコメントデータのリスト．先頭はノイズデータなので[1:]で保存
        for samp in dics['continuationContents']['liveChatContinuation']['actions'][1:]:
            d = {}
            try:
                samp = samp['replayChatItemAction']['actions'][0]['addChatItemAction']['item']
                if 'liveChatPaidMessageRenderer' in samp:
                    d['message'] = samp['liveChatPaidMessageRenderer']['message']['simpleText']
                    t = samp['liveChatPaidMessageRenderer']['timestampText']['simpleText']
                    d['timestamp'] = convert_time(t)
                    p = samp['liveChatPaidMessageRenderer']['purchaseAmountText']['simpleText']
                    d['purchase'] = int(p[1:])
                else:
                    d['message'] = samp['liveChatTextMessageRenderer']['message']['simpleText']
                    t = samp['liveChatTextMessageRenderer']['timestampText']['simpleText']
                    d['timestamp'] = convert_time(t)
            except:
                continue
            comment_data.append(d)
    return comment_data


def convert_time(input_t):
    t = list(map(int, input_t.split(':')))
    if len(t) == 2:
        if input_t[0] == '-':
            t = 0
        else:
            t = 60 * t[0] + t[1]
    else:
        t = 60 * 60 * t[0] + 60 * t[1] + t[2]
    return t


def find_highlight(comment_data, interval=10, grass_num=9, margin=10):
    '''
    interval この秒数以内であれば同一の見どころ
    grass_num 見どころとする草コメント数
    margin はじめて草コメントがあった箇所からマージンを取る
    '''
    time = -11
    cnt = 0
    purchase_total = 0
    purchase_num = 0
    point = []
    for c in comment_data:
        m = c['message']
        if m[-1] == '草' or m[-1] == 'w':
            cnt += 1
            if c['timestamp'] - time > interval:
                time = c['timestamp']
                point.append([time, 1])
            else:
                time = c['timestamp']
                point[-1][1] += 1
        if 'purchase' in c:
            purchase_total += c['purchase']
            purchase_num += 1

    # pprint.pprint(point)

    # 投稿するコメントを生成
    comment = '見どころ\n'
    for c in point:
        if c[1] > grass_num:
            comment += (inverse_convert_time(c[0], margin) + f' 草×{c[1]}\n')
    total = len(comment_data)
    minute_speed = round(len(comment_data) /
                         (comment_data[-1]['timestamp'] / 60), 2)
    comment += f'\n総コメント数 {total}\n総草コメント数 {cnt}\n1分あたりのコメント数 {minute_speed}'
    return comment


def inverse_convert_time(t, margin):
    if t - margin > 0:
        m, s = divmod(t - margin, 60)
        h, m = divmod(m, 60)
    else:
        m, s = divmod(t, 60)
        h, m = divmod(m, 60)

    if h > 0:
        return f'{h}:{m:02}:{s:02}'
    else:
        return f'{m}:{s:02}'


if __name__ == '__main__':
    target_url = sys.argv[1]
    filename = 'comment/' + target_url.split('/')[-1] + '.txt'
    if os.path.isfile(filename):
        with open(filename, 'r') as f:
            comment_data = ast.literal_eval(f.read())
    else:
        comment_data = get_comment(target_url)
        with open(filename, 'w') as f:
            f.write(str(comment_data))

    comment = find_highlight(comment_data, interval=1, grass_num=20)
    print(comment)
