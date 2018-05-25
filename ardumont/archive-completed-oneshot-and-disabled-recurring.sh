#!/usr/bin/env bash

for y in {2016..2018}; do
    for m in {1..12}; do
        m_1=$((m + 1))

        if [ ${m_1} -gt 12 ]; then
            y_1=$((y + 1))
            m_1=1
        else
            y_1=$y
        fi

        if [ $m -lt 10 ]; then
            m="0${m}"
        fi

        if [ $m_1 -lt 10 ]; then
            m_1="0${m_1}"
        fi

        cmd="python3 -m swh.scheduler.cli task archive --after "${y}-${m}-01" --before "${y_1}-${m_1}-01" --verbose --bulk-index 10"
        echo $cmd
        $cmd
    done
done
