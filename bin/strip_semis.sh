#!/bin/bash
#
# meta-sweeper - for performing parametric sweeps of simulated
# metagenomic sequencing experiments.
# Copyright (C) 2016 "Matthew Z DeMaere"
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

if [ $# -ne 1 ]
then
    echo "Usage: [fasta file]"
    exit 1
fi

sed -i -r 's/^(>[^;]+); $/\1/' $1
