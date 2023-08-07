#!/bin/bash
# This script splits japanese sentence by mecab.
#
# 20.03.26
# Hyungwon Yang
# NAMZ labs
#
# version history
# 20.05.18: no tag option is added.

pron_opt=false
tag_opt=false
nj=1
usage="=======================================================\n\
\t                   USAGE : run_japanese_mecab.sh         \n\
=======================================================\n\
\t*** OPTION ARGUMENT ***\n\
-h  | --help    : Print the direction.\n\
-nj | --num-job : multi threading process. default: 1\n\
-np | --no-pron : Remove pronunciation part in mecab result. default: false\n\
-nt | --no-tag  : Remove all the tag information that includes pronunciation and POS. default: false\n\n\
\t*** USAGE ***\n\
bash run_japanese_mecab.sh [option] [input: japansese text file] [output: save text file]\n\
bash run_japanese_mecab.sh --no-pron text_file save_file\n"

# input and option arguments
arg_num=$#
while [ $arg_num -gt 0 ] ; do 
  case "$1" in
    -h) echo -e $usage && exit; break ;;
    -nj) nj=$2; shift 2; arg_num=$((arg_num-1));;
    -np) pron_opt=true; shift; arg_num=$((arg_num-1)) ;;
    -nt) tag_opt=true; shift; arg_num=$((arg_num-1)) ;;

    --help) echo -e $usage && exit; break ;;
    --num-job) nj=$2; shift 2; arg_num=$((arg_num-1));;
    --no-pron) pron_opt=true; shift; arg_num=$((arg_num-1)) ;;
    --no-tag) tag_opt=true; shift; arg_num=$((arg_num-1)) ;;
    -*) echo -e "*** UNKNOWN OPTION: $1 ***\n"$usage ; exit  ;;
    --*) echo -e "*** UNKNOWN OPTION: $1 ***\n"$usage ; exit ;;
      *) break ;;
  esac
done 

if [ $# -ne 2 ]; then
   echo -e $usage  && exit 1
fi

if [ $tag_opt == true ]; then
    pron_opt=true;
fi

# input check
input_text=$1
if [ ! -f $input_text ]; then 
    echo "$input_text is not a text format." && exit 1
fi

save_file=$2
if [ -f $save_file ]; then
    while true; do
	read -p "$save_file is already saved. would you like to overwrite it? : " user_answer
	usr_val=`echo $user_answer | tr '[:upper:]' '[:lower:]'`
	if [ $usr_val == "yes" ] || [ $usr_val == "y" ]; then
	    rm $save_file
	    break
	elif [ $usr_val == "no" ] || [ $usr_val == "n" ]; then
	    break
	else
	    echo "please answer yes(y) or no(n)."
	fi
    done
fi

# mecab environment.
mecab_cmd=/home/hyung8758/hdd2tb/LM_exp/japlm_exp/japanese_lexicon/mecab-0.996/mecab_bin/bin/mecab
mecab_dict=/home/hyung8758/hdd2tb/LM_exp/japlm_exp/japanese_lexicon/mecab-0.996/mecab_bin/lib/mecab/dic/ipadic_utf-8

# check mecab.
if [ ! -e $mecab_cmd ]; then
    echo "MECAB COMMAND: $mecab_cmd is not runnable. please check yhour mecab command path." && exit 1
fi
if [ ! -e $mecab_dict ]; then
    echo "MECAB DICTIONARY: $mecab_dict not exist. please check yhour mecab dictionary path." && exit 1
fi
echo "mecab checked."

# progress bar
function ProgressBar {
# Process data
    let _progress=(${1}*100/${2}*100)/100
    let _done=(${_progress}*4)/10
    let _left=40-$_done
# Build progressbar string lengths
    _fill=$(printf "%${_done}s")
    _empty=$(printf "%${_left}s")

# 1.2 Build progressbar strings and print the ProgressBar line
# 1.2.1 Output example:                           
# 1.2.1.1 Progress : [########################################] 100%
printf "\rProgress : [${_fill// /#}${_empty// /-}] ${_progress}%%"
}

# multi threading
tmp_dir=`mktemp -d`
if [ -d $tmp_dir ]; then
    rm -rf $tmp_dir
fi
mkdir $tmp_dir

# split jobs.
line_num=`wc -l $input_text | awk '{print $1}'`
echo "total lines: $line_num"
split_line=$((line_num/nj))
while [ $split_line -eq 0 ]; do
    nj=$((nj-1))
    split_line=$((line_num/nj))
    echo "number of threading is larger than the line number of input text. Reduce num-job values to $nj."
done
remain=$((line_num%nj))

for snj in `seq 1 $nj`; do
    mkdir -p $tmp_dir/work_$snj
done


# distribute text lines.
start_idx=1
last_idx=0
for idx in `seq 1 $nj`; do
    last_idx=$((last_idx+split_line))
    sed -n "$start_idx,$last_idx"p $input_text > $tmp_dir/work_$idx/split.txt
    start_idx=$((start_idx+split_line))
done

# add remain text to last nj.
if [ $remain -ne 0 ]; then
    start_idx=$((last_idx+1))
    last_idx=$((start_idx+remain-1))
    sed -n "$start_idx,$last_idx"p $input_text >> $tmp_dir/work_$nj/split.txt
fi

# mecab process
function ProcessMecab {
    mecab_cmd=$1
    mecab_dict=$2
    pron_opt=$3
    tag_opt=$4
    while IFS= read -r line; do
	# echo "text: $line"
	# line_now=$((line_now+1))
	# ProgressBar $line_now $line_num
	final_line=
	TMPNAME=`mktemp`
	echo $line | $mecab_cmd -d $mecab_dict > $TMPNAME
        # for m_result in `echo $line | $mecab_cmd -d $mecab_dict`; do
	while IFS= read -r m_result; do
	    pre_cut=`echo $m_result | tr '\t' ',' | tr '*' '-' | tr ',' ' '`
	    # 1st column: japanese word
	    main_word=`echo $pre_cut | awk '{print $1}'`
	    # 2nd column: word pronunciation
	    pron_part=`echo $pre_cut | awk '{print $10}'`
	    # 3rd column: part of speech
	    sub_part=
	    if [ $tag_opt == false ]; then
		if [[ `echo $pre_cut | awk '{print $2}'` != "-" ]]; then
		    sub_part+=`echo $pre_cut | awk '{print $2}'`
		fi
		if [[ `echo $pre_cut | awk '{print $3}'` != "-" ]]; then
		    sub_part+="/"`echo $pre_cut | awk '{print $3}'`
		fi
		if [[ `echo $pre_cut | awk '{print $4}'` != "-" ]]; then
		    sub_part+="/"`echo $pre_cut | awk '{print $4}'`
		fi
		if [[ `echo $pre_cut | awk '{print $5}'` != "-" ]]; then
		    sub_part+="/"`echo $pre_cut | awk '{print $5}'`
		fi
		if [ $pron_opt == true ]; then
		    final_word=$main_word"+"$sub_part
		else
		    final_word=$main_word"+"$pron_part"+"$sub_part
		fi
	    else
		final_word=$main_word
	    fi
            final_line+=$final_word" "
	done  < $TMPNAME
	rm $TMPNAME
	# save each mecab processed line.
	echo $final_line | awk '{$NF=""; print $0}' | sed 's/ $//g'  >> $6
    done < $5
}

# running mecab
for run_j in `seq 1 $nj`; do
    ProcessMecab $mecab_cmd $mecab_dict $pron_opt $tag_opt $tmp_dir/work_$run_j/split.txt $tmp_dir/work_$run_j/mecab_result.txt &
done
wait

# combine all results.
for final_idx in `seq 1 $nj`; do
    cat $tmp_dir/work_$final_idx/mecab_result.txt >> $save_file
done

# sanity check
mecab_num=`wc -l $save_file| awk '{print $1}'`
if [ $line_num -ne $mecab_num ]; then
    echo -e "WARNING: 입력한 문장 개수와 mecab 결과물의 문장 개수가 일치하지 않습니다. \n -nj 옵션이 너무 커서 cpu 사용량이 과도할 경우 이러한 문제가 발생할 수 있으니, -nj 옵션을 줄여서 다시 실행해 주시기 바랍니다." 
fi
# remove tmp directory after mecab process.
rm -rf $tmp_dir

echo -e "\nDONE"	
