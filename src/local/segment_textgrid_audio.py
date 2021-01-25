"""
This script segments audio file based on textgrid information.
If Sentence tier is prepared in a TextGrid file, then this script will find every sentence string, except <SIL> and empty string, 
and split a paired audio file using the start and end time information in the TextGrid.
Final output will be a pair of sentence text and split auido file. 

Hyungwon Yang
21.01.13
"""

import os
import sys
import re
import optparse

# Arguments check.
parser = optparse.OptionParser()
parser.add_option("-n","--interval_tier", dest="tier_name", default="Sentence",
                  help="IntervalTier name for spliting audio file. defualt: Sentence")
parser.add_option("-t","--split_type", dest="split_type", default="tier",
                  help="spliting audio file by each 'tier' or 'sil' information." )
parser.add_option("-d","--split_silence_duration", dest="split_sil_dur", default=0.35, type="float",
                  help="Silence duration to be used for spliting audio file.")
parser.add_option("-s","--silence_duration", dest="sil_dur", default=1.0, type="float",
                  help="Duration of the silence padding before and after the word or sentence. Given duration will be the maximum value.")

(options,args) = parser.parse_args()
tier_name = options.tier_name
split_type = options.split_type
split_sil_dur = options.split_sil_dur
sil_dur = options.sil_dur

# input argument.
if len(args) != 3:
    print("usage: python segment_textgrid_audio.py [input: wav file] [input: TextGrid file] [output: save folder]")
    sys.exit()

if (split_type != 'tier' and split_type != 'sil'):
    print("split type ({}) is not recognizable.".format(split_type))
    print("Provide 'tier', if the audio should be split by each tier word or sentence.")
    print("Provide 'sil', if the audio should be split when <SIL> appeared.")
    sys.exit()
    
audio_file = args[0]
tg_file = args[1]
save_path = args[2]

file_name = re.sub(".wav", "", os.path.basename(audio_file))

# save directory check.
if not os.path.exists(save_path):
    os.mkdir(save_path)

# extract textgrid information.
with open(tg_file, 'r', encoding='utf-8') as txt:
    tg_txt = txt.readlines()
    for idx, each_w in enumerate(tg_txt):
        tg_txt[idx] = re.sub('"|\n','',each_w)
    # get tier_name start idx information.
    for idx, word in enumerate(tg_txt):
        if tier_name in word:
            tier_start_idx = idx
            break

# get basic information.
tier_range = int(tg_txt[tier_start_idx+3]) # The number of words. 
pad_range = len(tg_txt[tier_start_idx+3]) # It will be used in zero padding.
word_start_idx = tier_start_idx+6 # first word index
word_end_idx = word_start_idx + ((tier_range) * 3) 

pad_idx = 1
print("[OPTION] tier_name: {}, split_type: {}, split_sil_dur: {} sec, sil_dur: {} sec".format(tier_name, split_type, split_sil_dur, sil_dur))
# split by each tier.
if split_type == 'tier':
    # print("use tier information.")
    for w_idx in range(word_start_idx, word_end_idx, 3):
        word = tg_txt[w_idx]
        # save audio and text file if only word is not empty or silence
        if word and word != "<SIL>":
            # print("extracing text information : {} ".format(tg_txt[w_idx]))
            zero_pad_tag = '%0'+str(pad_range)+'d'
            zero_pad_tag = zero_pad_tag  % pad_idx
            # get the time duration and padding with silence if <SIL> exists
            start_time = float(tg_txt[w_idx-2])
            dur = float(tg_txt[w_idx-1]) - start_time
            prv_dur = 0
            post_dur = 0
            prv_word = tg_txt[w_idx-3]
            post_word = tg_txt[w_idx+3]
            if prv_word == "<SIL>":
                prv_dur = float(tg_txt[w_idx-4]) - float(tg_txt[w_idx-5])
                if prv_dur > sil_dur:
                    prv_dur = sil_dur
                start_time -= prv_dur
                dur += prv_dur
            if post_word == "<SIL>":
                post_dur = float(tg_txt[w_idx+2]) - float(tg_txt[w_idx+1])
                if post_dur > sil_dur:
                    post_dur = sil_dur
                dur += post_dur
            # save audio file.
            audio_save_name = '/'.join([save_path,file_name+"-trim-"+zero_pad_tag+".wav"])
            cmd = "sox " + audio_file + " " + audio_save_name + " trim {:.2f} {:.2f}".format(start_time, dur)
            # print("command: {}".format(cmd))
            os.system(cmd)
            # save text file.
            txt_save_name = '/'.join([save_path,file_name+"-trim-"+zero_pad_tag+".txt"])
            with open(txt_save_name, 'w', encoding='utf-8') as wrt:
                wrt.write(word)
            pad_idx += 1
# split by <SIL>.
elif split_type == 'sil':
    # print("use <SIL> information.")
    total_word = ""
    start_idx = 0
    for w_idx in range(word_start_idx, word_end_idx, 3):
        word = tg_txt[w_idx]
        # save audio and text file if only word is not empty or silence
        if word != "<SIL>":
            # print("extracing text information : {} ".format(tg_txt[w_idx]))
            total_word += " "
            total_word += word
            # get the time duration and padding with silence if <SIL> exists
            if start_idx == 0:
                start_time = float(tg_txt[w_idx-2])
                prv_word = tg_txt[w_idx-3]
                if prv_word == "<SIL>":
                    prv_dur = float(tg_txt[w_idx-4]) - float(tg_txt[w_idx-5])
                    if prv_dur > sil_dur:
                        prv_dur = sil_dur
                    start_time -= prv_dur
            dur = float(tg_txt[w_idx-1]) - start_time
            # check next word inforamtion.
            try:
                post_w_idx = w_idx+3
                post_word = tg_txt[post_w_idx]
            except:
                print("<SIL> is not found at the end of the textgrid file. Ignore this file.")
                sys.exit()
            # if next word is <SIL>, decide whether to split the audio or not.
            if post_word == "<SIL>":
                post_word_start = float(tg_txt[post_w_idx-2])
                post_word_end = float(tg_txt[post_w_idx-1])
                post_dur = post_word_end - post_word_start
                if post_dur >= split_sil_dur:
                    # need to be split.
                    if post_dur > sil_dur:
                        post_dur = sil_dur
                    dur += post_dur
                    zero_pad_tag = '%0'+str(pad_range)+'d'
                    zero_pad_tag = zero_pad_tag  % pad_idx
                    audio_save_name = '/'.join([save_path,file_name+"-trim-"+zero_pad_tag+".wav"])
                    cmd = "sox " + audio_file + " " + audio_save_name + " trim {:.2f} {:.2f}".format(start_time, dur)
                    # print("command: {}".format(cmd))
                    os.system(cmd)
                    # save text file.
                    total_word = re.sub("^ | $","",total_word)
                    if post_w_idx != word_end_idx - 3:
                        total_word += " ,"
                    else:
                        total_word += " ."
                    txt_save_name = '/'.join([save_path,file_name+"-trim-"+zero_pad_tag+".txt"])
                    with open(txt_save_name, 'w', encoding='utf-8') as wrt:
                        wrt.write(total_word)
                    pad_idx += 1
                    # reset variables.
                    start_idx = 0
                    total_word = ""
                else:
                    # skip this sil.
                    start_idx += 1
                    continue
                   
            # next word is not <SIL>, go to next word.
            else:
                start_idx += 1
                continue
            
print("DONE")