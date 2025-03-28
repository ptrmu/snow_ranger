#!/bin/bash
current_date=$(date +"%Y%m%d")
python3 ~/Work/SnowRanger/read_ranger_mqtt.py --mqtt-user peter --mqtt-password carmal --serial-gpio 18 &>> ~/Work/SnowRanger/rm_$current_date.log
python3 ~/Work/SnowRanger/read_ranger_send_mqtt.py --mqtt-user peter --mqtt-password carmal --serial-port /dev/ttyS0 --mqtt-topic snowdata/921a_15 &>> ~/Work/SnowRanger/rs_$current_date.log
