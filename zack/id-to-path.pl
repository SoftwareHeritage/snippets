#!/usr/bin/perl
use strict;
while (my $l = <>) {
    chomp $l;
    $l = substr($l, -40);

    print "/srv/softwareheritage/objects/";
    print substr($l, 0, 2), "/";
    print substr($l, 2, 2), "/";
    print substr($l, 4, 2), "/";
    print $l, "\n";
}
