"""
Copyright 2016  Korea University & EMCS Labs  (Author: Hyungwon Yang)
Apache 2.0

*** Introduction ***
This script adjust floating precision in raw_ali.ctm file

*** USAGE ***
Ex. python fix_ctm_float.py $ctm_file $adjusted_ctm_file

"""

import sys

if len(sys.argv) != 3:
    print("Input arguments are incorrectly provided. Two arguments should be assigned.")
    print("1. ctm file.")
    print("2. adjusted_ctm file.")
    print("*** USAGE ***")
    print("Ex. python fix_ctm_float.py $ctm_file $adjusted_ctm_file")
    raise ValueError('RETURN')


data_file = sys.argv[1]
save_file = sys.argv[2]


# import raw ctm file.
with open(data_file,'r') as txt:
    ctm = txt.readlines()

    fixed_ctm = []
    for idx, line in enumerate(ctm):
        chunk = line.split(' ')
        if idx == 0:
            result = ' '.join(chunk)
            fixed_ctm.append(result)
        else:
            fix_chunk = fixed_ctm[idx-1].split(' ')
            prev_init = fix_chunk[2]
            prev_dur = fix_chunk[3]
            cur_init = round(float(prev_init) + float(prev_dur),2)
            # fix init val
            chunk[2] = str(cur_init)
            result = ' '.join(chunk)
            fixed_ctm.append(result)

# save the fixed ctm file.
with open(save_file,'w') as wrt:
    for line in fixed_ctm:
        wrt.write(line)

