#!/bin/bash
current_date=$(date +"%Y%m%d")
python3 ~/Work/SnowRanger/read_ranger.py >> ~/Work/SnowRanger/rr_$current_date.log
