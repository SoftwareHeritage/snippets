How to use:

1. get unsorted_inventory.txt.gz
2. sort it (--temporary-directory is needed if /tmp doesn't have >100GB free):
   pv unsorted_inventory.txt.gz | pigz -d | LANG=C sort --temporary-directory=$HOME/tmp/ --parallel=12 --buffer-size=1G --compress-program=pigz | pv --wait --line-mode | pigz > sorted_inventory.txt.gz
3. convert hex digests to binary:
   pv sorted_inventory.txt.gz | pigz -d | python3 hash_txt_to_bytes.py > /srv/softwareheritage/cassandra-test-0/scratch/sorted_inventory.bin
