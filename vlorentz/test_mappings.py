import os
import os.path
import pprint

from swh.indexer.metadata_dictionary import MAPPINGS

BASE_DIR = os.path.expanduser('~/datasets/')

CATEGORIES = {
    ('GemspecMapping', 'gemspec'),
    ('PythonPkginfoMapping', 'pkginfo'),
}

def test_category(mapping_name, category):
    mapping = MAPPINGS[mapping_name]
    dataset_dir = os.path.join(BASE_DIR, category)

    for filename in os.listdir(dataset_dir):
        path = os.path.join(dataset_dir, filename)
        with open(path, 'rb') as fd:
            file_content = fd.read()
        print('Parsing {}:'.format(path))
        pprint.pprint(mapping.translate(file_content))

def main():
    for (mapping_name, category) in CATEGORIES:
        test_category(mapping_name, category)

if __name__ == '__main__':
    main()
