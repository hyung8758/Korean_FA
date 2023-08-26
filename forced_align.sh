#!/bin/bash
#
# Copyright 2016 Media Zen & 
#				 Korea University (author: Hyungwon Yang) v1.6
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# *** INTRODUCTION ***
# This is the forced alignment toolkit developed by EMCS labs.
# Run this script in the folder in which force_align.sh presented.
# It means that the user needs to nevigate to this folder in linux or
# mac OSX terminal and then run this script. Otherwise this script
# won't work properly.
# Do not move the parts of scripts or folders or run the main script
# from outside of this folder.

set -e
set -u
# set -o pipefail

# Kaldi directory ./kaldi
kaldi=/home/kaldi

# Number of jobs(just fix it to one)
fa_nj=1
fail_num=0

# Check kaldi directory.
if [ ! -d $kaldi ]; then
	echo -e "ERROR: Kaldi directory is not found. Please reset the kaldi directory by editing force_align.sh.\nCurrent kaldi directory : $kaldi" && exit 1
fi

# Option Parsing and checking. 
# Option default.
tg_word_opt=none
tg_phone_opt=none
tg_skip_opt=
usage="=======================================================\n\
\t         The Usage of Korean Foreced Aligner.         \n\
=======================================================\n\
\t*** OPTION ARGUMENT ***\n\
-h  | --help    : Print the direction.\n\
-nj | --num-job : This option splits total files into small subsets and align them in parallel.\n\
-s  | --skip    : This option excludes wave data from alignment which already have TextGrid files.\n\
-nw | --no-word : This opiton excludes word label from TextGrid.\n\
-np | --no-phone: This option excludes phone label from TextGrid.\n\
\t*** INPUT ARGUMENT ***\n\
File directory. ex) example/my_record\n\n\
\t*** USAGE ***\n\
bash forced_align.sh [option] [data directory]\n\
bash forced_align.sh -np example/my_record\n"

if [ $# -gt 5 ] || [ $# -lt 1 ]; then
   echo -e $usage  && exit
fi

# find optional variables.
arg_num=$#
while [ $arg_num -gt 0 ] ; do 
    case "$1" in
	-h) echo -e $usage && exit; break ;;
	-s) tg_skip_opt="--skip"; shift; arg_num=$((arg_num-1)) ;;
	-nj) fa_nj=$2; shift 2; arg_num=$((arg_num-2)) ;;
	-nw) tg_word_opt="--no-word"; shift; arg_num=$((arg_num-1)) ;;
	-np) tg_phone_opt="--no-phone"; shift; arg_num=$((arg_num-1)) ;;

	--help) echo -e $usage && exit; break ;;
	--skip) tg_skip_opt="--skip"; shift; arg_num=$((arg_num-1)) ;;
	--num-nj) fa_nj=$2; shift 2; arg_num=$((arg_num-2)) ;;
	--no-word) tg_word_opt="--no-word"; shift; arg_num=$((arg_num-1)) ;; 
	--no-phone) tg_phone_opt="--no-phone"; shift; arg_num=$((arg_num-1)) ;;
	-*) echo -e "*** UNKNOWN OPTION: $1 ***\n"$usage ; exit  ;;
	--*) echo -e "*** UNKNOWN OPTION: $1 ***\n"$usage ; exit ;;
	*) break ;;
    esac
done

# num job variable should contain integer.
if ! [[ $fa_nj =~ ^[0-9]+$ ]] ; then
    echo "ERROR: -nj or --num-jb is not a number. Please provide a number for this option."; exit 1
fi

# find input variables.
if [ $# -eq 0 ]; then
    echo -e $usage
    exit 1
fi

# Check data_dir
source path.sh $kaldi
alias realpath="perl -MCwd -e 'print Cwd::realpath(\$ARGV[0]),qq<\n>'"
data_dir=`realpath $1`
if [ ! -d $data_dir ]; then
    echo "ERROR: $data_dir is not present. Please check the data directory."  && exit
fi

log_dir=log/fa_log
tmp_dir=`mktemp -d`
trap "[ -d $tmp_dir ] && rm -rf $tmp_dir" SIGINT
# make log directory with no previous log.
if [ -d $log_dir ]; then
    rm -rf $log_dir/*
else
    mkdir -p $log_dir
fi

# Find audio and text files.
wav_list=`find $data_dir -type f \( -iname "*.wav" \)`
txt_list=`find $data_dir -type f \( -iname "*.txt" \)`
[[ -z "$wav_list" ]] && wav_num=0 || wav_num=$(echo "$wav_list" | wc -l)
[[ -z "$txt_list" ]] && txt_num=0 || txt_num=$(echo "$txt_list" | wc -l)
[[ $wav_num -eq 0 ]] && echo "Audio files are not found." && exit
[[ $txt_num -eq 0 ]] && echo "Text files are not found." && exit
# check the number of files.

if [ "$tg_skip_opt" == "--skip" ]; then
    echo -e "Skipping option is activated.\nWave data which already have TextGrid files will be excluded from alignment list."
    # Wave file which has a textgrid will not be aligned.
    # Check wave file list and select files that have not textgrids.
    for wav in $wav_list; do
        wav_name=`echo $wav | sed "s/wav$//g"`
        txt_pair=`echo $wav | sed "s/wav$/txt/g"`
        # textgird 및 txt가 있을 경우.
        if [ ! -f $wav_name.TextGrid ] && [ -f $txt_pair ]; then
            tmp_wav_list+="$wav "
            tmp_txt_list+="$txt_pair "
        fi
    done
else
    # Find audio and text files.
    for wav in $wav_list; do
        txt_pair=`echo $wav | sed "s/wav$/txt/g"`
        # pair 텍스트가 있는 경우.
        if [ -f $txt_pair ]; then
            tmp_wav_list+="$wav "
            tmp_txt_list+="$txt_pair "
        fi
    done
fi
# check auio number
wav_list=$tmp_wav_list
txt_list=$tmp_txt_list
[[ -z "$wav_list" ]] && wav_num=0 || wav_num=$(echo $wav_list | sed 's/ /\n/g'| wc -l)
[[ -z "$txt_list" ]] && txt_num=0 || txt_num=$(echo $txt_list | sed 's/ /\n/g'| wc -l)

# check text file.
python src/local/check_text.py $tg_skip_opt $data_dir || exit 1

# Check if each audio file has a matching text file.
if [ $wav_num -ne $txt_num ]; then
    echo "ERROR: The number of audio and text files are not matched. Please check the input data." 
    echo "Audio list: "$wav_list
    echo "Text  list: "$txt_list
    exit
fi

# Split jobs.
split_nj=$((wav_num/fa_nj))
remain=$((wav_num%fa_nj))
if [ $split_nj -ne 0 ]; then
    for snj in `seq 1 $split_nj`; do
	    mkdir -p $tmp_dir/work_$snj/source
    done
fi
total_j=$split_nj
if [ $remain -ne 0 ]; then
    mkdir -p $tmp_dir/work_$((split_nj+1))/source
    total_j=$((total_j+1))
fi

# distribute source files based on wav info.
j=1
for each_wav in $wav_list; do 
    cp $each_wav $tmp_dir/work_$j/source
    txt_pair=`echo $each_wav | sed 's/wav$/txt/g'`
    cp $txt_pair $tmp_dir/work_$j/source
    if [ $j -eq $total_j ]; then
	    j=1
    else
	    j=$((j+1))
    fi
done

echo ===================================================================
echo "                    Korean Forced Aligner                        "    
echo ===================================================================
echo "The number of audio files: $wav_num"
echo "The number of text files: $txt_num"

# Main loop for alignment.
job_idx=1
for turn in `seq 1 $total_j`; do
    subwav_list=`ls $tmp_dir/work_$turn/source | grep .wav`
    # pre-processing and alining wave files.
    echo "Aligning $subwav_list"
    for sub_wav in $subwav_list; do
	sub_txt=`echo $sub_wav | sed 's/wav/txt/g'`
    bash src/local/main_fa.sh $kaldi $job_idx $log_dir $data_dir $tmp_dir/work_$turn/source/$sub_wav $tmp_dir/work_$turn/source/$sub_txt $tg_word_opt $tg_phone_opt &
	job_idx=$((job_idx+1))
    done
    wait
done

# count fail trials.
fail_num=`cat $log_dir/history.log | grep FAIL | wc -l`
# sort history.log
cat $log_dir/history.log | sort > $log_dir/tmp.log; mv $log_dir/tmp.log $log_dir/history.log
# Print result information.
echo "===================== FORCED ALIGNMENT FINISHED  =====================" | tee    $log_dir/result.log
echo "** Result Information on $(date) **				    " | tee -a $log_dir/result.log
echo "Total Trials:" $wav_num						      | tee -a $log_dir/result.log
echo "Success     :" $((wav_num - fail_num))				      | tee -a $log_dir/result.log
echo "Fail        :" $fail_num						      | tee -a $log_dir/result.log
echo "----------------------------------------------------------------------" | tee -a $log_dir/result.log
echo "Result      : $((wav_num - fail_num)) / "$wav_num" (Success / Total)"   | tee -a $log_dir/result.log
if [ $fail_num -gt 0 ]; then 
    echo "To check the failed results, refer to the $log_dir directory."
fi
echo

echo "DONE"

# remove processed directoies.
rm -rf $tmp_dir 
# if [ -d bin ]; then
#     rm -rf bin
# fi
