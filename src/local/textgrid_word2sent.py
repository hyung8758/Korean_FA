'''
generate a sentence tier in the FA text format.

Hyungwon Yang
NAMZ Labs

19.08.22
edited 21.01.05
'''

import os
import re
import sys
import optparse

# Arguments check.
parser = optparse.OptionParser()
parser.add_option("-p","--show-pause", action="store_true", dest="sym_pause", default=False,
                  help="Find pause duration in the sentence and mark the place with a symbol.")
parser.add_option("-d","--pause_duration", dest="sym_pause_dur", default=0.35, type="float",
                  help="pause duration threshold when mark a pause symbol inside the sentence. ")
parser.add_option("-n","--pause_symbol_max", dest="sym_max", default=2, type="int",
                  help="no matter how pause duration long, symbols will be used up to max value.")
parser.add_option("-t","--pause_symbol_type", dest="sym_type", default=",",
                  help="marking symbol type.")

sil_sym = '<SIL>'
sil_insert_form = '"' + sil_sym + '"' + '\n'
(options,args) = parser.parse_args()
sym_pause = options.sym_pause
sym_pause_dur = options.sym_pause_dur
sym_max = options.sym_max
sym_type = options.sym_type

if len(args) != 3:
    print("USAGE: python3 textgrid_word2sent.py [input: sentence text] [input word level TextGrid] [output: sentence level TextGrid]")
    exit(1)

origin_text = args[0]
tg_text = args[1]
tg_out = args[2]

# read original text file and pre processing.
with open(origin_text,'r',encoding='utf-8') as txt:
    ori_new_lines = txt.readlines()
    ori_lines = [None] * len(ori_new_lines)
    for idx, line in enumerate(ori_new_lines):
        tmp_line = re.sub('[0-9]','',line)
        tmp_line = re.sub('X', '', tmp_line)
        tmp_line = re.sub('[@]+','',tmp_line)
        tmp_line = re.sub('[\.\,\?]','',tmp_line)
        tmp_line = re.sub('[ ]+', ' ', tmp_line)
        tmp_line = tmp_line.split()
        ori_lines[idx] = tmp_line

# read original TextGrid file and extract 'word' tier information.
with open(tg_text, 'r', encoding='utf-8') as tg:
    tg_new_lines = tg.readlines()
    # find empty line.
    space_num = 0
    for line in tg_new_lines:
        if not line.strip():
            space_num += 1
    new_tg_lines = [None] * (len(tg_new_lines) - space_num)
    tg_line_num = len(new_tg_lines)
    line_idx = 0
    # contain only not empty sentence.
    for line in tg_new_lines:
        if line.strip():
            new_tg_lines[line_idx] = line
            line_idx += 1
    
    word_idx = 0
    # find word tier start index
    for idx, line in enumerate(new_tg_lines):
        if re.findall('word',line):
            word_idx = idx
            break
    # readjust word_idx to direct start word time which is 0.
    if word_idx == 0:
        print('TextGrid has no word tier.')
        exit(1)
    word_idx += 4
    # make word tier.
    tg_line_num = len(new_tg_lines)
    word_num = tg_line_num - word_idx
    word_lines = [None] * word_num
    # print("word_lines: {}".format(len(word_lines)))
    num = 0
    for idx in range(word_idx,tg_line_num):
        tmp_line = new_tg_lines[idx]
        word_lines[num] = re.sub('[\n|"]','',tmp_line)
        num += 1

# match text and TextGrid to find sentences.
tg_idx = 2
fa_line_num = 0
total_line_num = ((len(ori_lines) + 2) * 3) + 13 # original sentence line number with time indices + first and last sil insert and intro information line numbers. 
matched_textgrid_list = [None] * total_line_num

# insert intro information.
total_idx = 0
print("Combine word information to make Sentence information.")
for tg_mark in range(5):
    if tg_mark != 2:
        matched_textgrid_list[total_idx] = (new_tg_lines[tg_mark])
        total_idx += 1
    else:
        matched_textgrid_list[total_idx] = "\n"
        total_idx += 1
        matched_textgrid_list[total_idx] = new_tg_lines[tg_mark]
        total_idx += 1

matched_textgrid_list[total_idx] = '1\n'
total_idx += 1
matched_textgrid_list[total_idx] = '\n'
total_idx += 1
matched_textgrid_list[total_idx] = '"IntervalTier"\n'
total_idx += 1
matched_textgrid_list[total_idx] = '"Sentence"\n'
total_idx += 1
matched_textgrid_list[total_idx] = new_tg_lines[2] # start time info
total_idx += 1
matched_textgrid_list[total_idx] = new_tg_lines[3] # end time info
total_idx += 1
matched_textgrid_list[total_idx] = str(fa_line_num)+'\n' # total sent + sil numbers
total_idx += 1

# write main sentence FA
for idx, sent in enumerate(ori_lines):
    # print("original sentence: {}".format(sent))
    time_box = []
    # 첫 sil symbol 넣기.
    if idx == 0:
        matched_textgrid_list[total_idx] = str(new_tg_lines[11])
        total_idx += 1
        matched_textgrid_list[total_idx] = str(new_tg_lines[12])
        total_idx += 1
        matched_textgrid_list[total_idx] = sil_insert_form
        total_idx += 1
        fa_line_num += 1
        tg_idx += 3
    # 첫 문장부터 마지막 문장까지 넣기.
    sent_box = []
    for w_idx, w in enumerate(sent):
        # print("tg idx: {}".format(tg_idx))
        # print('word and word_lines: {} : {}'.format(w,word_lines[tg_idx]))
        while w != word_lines[tg_idx]:
            # print("{} and {} mismatch!".format(w,word_lines[tg_idx]))
            # sil process 
            if sym_pause:
                if (w_idx != 0 and word_lines[tg_idx] == sil_sym):
                    sil_dur = float(word_lines[tg_idx - 1]) - float(word_lines[tg_idx - 2])
                    # print("sil duration: {:.2f}".format(sil_dur))
                    now_threshold = sym_pause_dur
                    for turn in range(sym_max):
                        if now_threshold < sil_dur:
                            sent_box.append(sym_type)
                        now_threshold += sym_pause_dur
            tg_idx += 3
            # print("what next: {} and {}".format(w,word_lines[tg_idx]))
            
        # handle same word occurred twice in the sentence.
        if w_idx != 0:
            if w == sent[w_idx-1]:
                tg_idx += 3
                time_box.append(float(word_lines[tg_idx - 2]))
                time_box.append(float(word_lines[tg_idx - 1]))
                sent_box.append(word_lines[tg_idx])
        # print('in sentenece tg_idx: {}'.format(tg_idx))
        time_box.append(float(word_lines[tg_idx - 2]))
        time_box.append(float(word_lines[tg_idx - 1]))
        sent_box.append(word_lines[tg_idx])
        tg_idx += 3
    fa_line_num += 1
    # print('sentence and times: {} {} {}'.format(sent_box,min(time_box),max(time_box)))
    matched_textgrid_list[total_idx] = str(min(time_box)) + '\n'
    total_idx += 1
    matched_textgrid_list[total_idx] = str(max(time_box)) + '\n'
    total_idx += 1
    matched_textgrid_list[total_idx] = '"' + ' '.join(sent_box) + '"' + '\n'
    total_idx += 1
    # 마지막 sil symbol 넣기.
    if idx == len(ori_lines) - 1:
        matched_textgrid_list[total_idx] = str(float(word_lines[tg_idx + 1]))+'\n'
        total_idx += 1
        matched_textgrid_list[total_idx] = new_tg_lines[3]
        total_idx += 1
        matched_textgrid_list[total_idx] =  sil_insert_form
        total_idx += 1
        # print('FINAL sentence and times: {} {} {}'.format(sent_box, min(time_box), max(time_box)))
        fa_line_num += 1

# finalize fa line number
start_idx = 15 # first word "<SIL>" appears
for w_idx in range(start_idx, total_line_num - 2, 3):
    cur_word_end_time = float(matched_textgrid_list[w_idx-1])
    next_word_start_time = float(matched_textgrid_list[w_idx+1])
    if cur_word_end_time != next_word_start_time:
        fa_line_num += 1
matched_textgrid_list[12] = str(fa_line_num) + "\n"

# save processed textgrid file.
print("Generating output TextGrid.")
with open(tg_out, 'w', encoding='utf-8') as wrt:

    for idx in range(start_idx-2):
        wrt.write(matched_textgrid_list[idx])
    
    for w_idx in range(start_idx, total_line_num - 2, 3):
        # print("searching idx: {}".format(w_idx))
        cur_word_end_time = float(matched_textgrid_list[w_idx-1])
        next_word_start_time = float(matched_textgrid_list[w_idx+1])
        # 문장사이에 sil 삽입이 필요 없는 경우.
        if cur_word_end_time == next_word_start_time:
            wrt.write(matched_textgrid_list[w_idx-2])
            wrt.write(matched_textgrid_list[w_idx-1])
            wrt.write(matched_textgrid_list[w_idx])
        else: # 문장 사이에 sil 삽입해야 할 경우.
            wrt.write(matched_textgrid_list[w_idx-2])
            wrt.write(matched_textgrid_list[w_idx-1])
            wrt.write(matched_textgrid_list[w_idx])
            # insert sil part
            wrt.write(matched_textgrid_list[w_idx-1])
            wrt.write(matched_textgrid_list[w_idx+1])
            wrt.write(sil_insert_form)
    # last part
    wrt.write(matched_textgrid_list[w_idx+1])
    wrt.write(matched_textgrid_list[w_idx+2])
    wrt.write(matched_textgrid_list[w_idx+3])
print("DONE")

