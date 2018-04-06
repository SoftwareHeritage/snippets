INSERT INTO chunking_method (algo, min_block_size, average_block_size, max_block_size, window_size) VALUES
    ('rabin', 2<<11, 2<<14, 2<<17, 48*1024),
    ('rabin', 2<<12, 2<<14, 2<<16, 48*1024),
    ('rabin', 2<<13, 2<<14, 2<<15, 32*1024),

    ('rabin', 2<<11, 2<<13, 2<<15, 16*1024),
    ('rabin', 2<<12, 2<<13, 2<<14, 16*1024),

    ('rabin', 2<<10, 2<<12, 2<<14, 8*1024),
    ('rabin', 2<<11, 2<<12, 2<<13, 8*1024),

    ('rabin', 2<<9, 2<<11, 2<<13, 4*1024),
    ('rabin', 2<<10, 2<<11, 2<<12, 4*1024),

    ('rabin', 2<<8, 2<<10, 2<<12, 2*1024),
    ('rabin', 2<<9, 2<<10, 2<<11, 2*1024),

    ('rabin', 2<<7, 2<<9, 2<<11, 1*1024),
    ('rabin', 2<<8, 2<<9, 2<<10, 1*1024),

    ('rabin', 2<<6, 2<<8, 2<<10, 512),
    ('rabin', 2<<7, 2<<8, 2<<9, 512)
ON CONFLICT DO NOTHING;

INSERT INTO chunking_method (algo, min_block_size, average_block_size, max_block_size, window_size)
    SELECT 'buzhash', min_block_size, average_block_size, max_block_size, window_size
    FROM chunking_method WHERE algo = 'rabin'
ON CONFLICT DO NOTHING;
