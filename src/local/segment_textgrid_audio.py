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
parser.add_option("-t","--interval-tier", dest="tier_name", default="Sentence",
                  help="IntervalTier name for spliting audio file. defualt: Sentence")


(options,args) = parser.parse_args()
tier_name = options.tier_name

# input argument.
if len(args) != 3:
    print("usage: python segment_textgrid_audio.py [input: wav file] [input: TextGrid file] [output: save folder]")
    sys.exit()

audio_file = sys.argv[1]
tg_file = sys.argv[2]
save_path = sys.argv[3]

file_name = re.sub(".wav", "", os.path.basename(audio_file))

# save directory check.
if not os.path.exists(save_path):
    os.mkdir(save_path)

# extract textgrid information.
with open(tg_file, 'r', encoding='utf-16') as txt:
    tg_txt = txt.readlines()
    for idx, each_w in enumerate(tg_txt):
        tg_txt[idx] = re.sub('"|\n','',each_w)
        # tg_txt[idx] = re.sub("\n","",each_w)
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
print("spliting audio file using {} tier information.".format(tier_name))
for w_idx in range(word_start_idx, word_end_idx, 3):
    word = tg_txt[w_idx]
    # save audio and text file if only word is not empty or silence
    if word and word != "<SIL>":
        # print("extracing text information : {} ".format(tg_txt[w_idx]))
        zero_pad_tag = '%0'+str(pad_range)+'d'
        zero_pad_tag = zero_pad_tag  % pad_idx
        start_time = float(tg_txt[w_idx-2])
        dur = float(tg_txt[w_idx-1]) - start_time
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

print("DONE")