#!/usr/bin/env python
"""
meta-sweeper - for performing parametric sweeps of simulated
metagenomic sequencing experiments.
Copyright (C) 2016 "Matthew Z DeMaere"

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import string
import os
from itertools import imap

import numpy as np
import scipy.stats as st
from Bio.Alphabet import IUPAC
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

"""
The following module was transcribed and adapted from the original project's C++ code:

ART -- Artificial Read Transcription, Illumina Q version
Authors: Weichun Huang 2008-2016
License: GPL v3
"""

def _clear_list(l):
    del l[:]

# path of this (Art.py) source file. It is expected that profiles are co-located with Art.
MODULE_PATH = os.path.dirname(os.path.abspath(__file__))

# A catalog of empirical profiles for Illumina machine types.
ILLUMINA_PROFILES = {
    'Emp100': ('Illumina_profiles/Emp100R1.txt',
               'Illumina_profiles/Emp100R2.txt'),
    'Emp36':('Illumina_profiles/Emp36R1.txt',
             'Illumina_profiles/Emp36R2.txt'),
    'Emp44': ('Illumina_profiles/Emp44R1.txt',
              'Illumina_profiles/Emp44R2.txt'),
    'Emp50': ('Illumina_profiles/Emp50R1.txt',
              'Illumina_profiles/Emp50R2.txt'),
    'Emp75': ('Illumina_profiles/Emp75R1.txt',
              'Illumina_profiles/Emp75R2.txt'),
    'EmpMiSeq250': ('Illumina_profiles/EmpMiSeq250R1.txt',
                    'Illumina_profiles/EmpMiSeq250R2.txt'),
    'EmpR36': ('Illumina_profiles/EmpR36R1.txt',
               'Illumina_profiles/EmpR36R2.txt'),
    'EmpR44': ('Illumina_profiles/EmpR44R1.txt',
               'Illumina_profiles/EmpR44R2.txt'),
    'EmpR50': ('Illumina_profiles/EmpR50R1.txt',
               'Illumina_profiles/EmpR50R2.txt'),
    'EmpR75': ('Illumina_profiles/EmpR75R1.txt',
               'Illumina_profiles/EmpR75R2.txt'),
    'HiSeq2500L125': ('Illumina_profiles/HiSeq2500L125R1.txt',
                      'Illumina_profiles/HiSeq2500L125R2.txt'),
    'HiSeq2500L150': ('Illumina_profiles/HiSeq2500L150R1.txt',
                      'Illumina_profiles/HiSeq2500L150R2.txt'),
    'HiSeq2500L150filt': ('Illumina_profiles/HiSeq2500L150R1filter.txt',
                          'Illumina_profiles/HiSeq2500L150R2filter.txt'),
    'HiSeq2kL100': ('Illumina_profiles/HiSeq2kL100R1.txt',
                    'Illumina_profiles/HiSeq2kL100R2.txt'),
    'HiSeqXPCRfreeL150': ('Illumina_profiles/HiSeqXPCRfreeL150R1.txt',
                          'Illumina_profiles/HiSeqXPCRfreeL150R2.txt'),
    'HiSeqXtruSeqL150': ('Illumina_profiles/HiSeqXtruSeqL150R1.txt',
                         'Illumina_profiles/HiSeqXtruSeqL150R2.txt'),
    'MiSeqv3L250': ('Illumina_profiles/MiSeqv3L250R1.txt',
                    'Illumina_profiles/MiSeqv3L250R2.txt'),
    'NextSeq500v2L75': ('Illumina_profiles/NextSeq500v2L75R1.txt',
                        'Illumina_profiles/NextSeq500v2L75R2.txt')
}

def get_profile(name):
    """
    Return the absolute path to a requested Illumina profile.
    :param name: the name of the profile.
    :return: absolute (full) path
    """
    assert name in ILLUMINA_PROFILES, 'Unknown profile name. Try one of: {0}'.format(
        ', '.join(ILLUMINA_PROFILES.keys()))

    return map(lambda pi: os.path.join(MODULE_PATH, pi), ILLUMINA_PROFILES[name])


def parse_error(quals, seq_read):
    """
    When analyzed, sequences are potentially modified by the simulated quality scores.
    :return: number of modified bases.
    """

    num_seq = len(quals)

    random_base = Art.random_base
    n_symb = EmpDist.N_SYMB
    prob_err = EmpDist.PROB_ERR

    # random values to test against, this is faster than invoking
    # the method each iteration.
    rvals = Art.UNIFORM(size=num_seq)

    for i in xrange(num_seq):
        # if we encounter an undefined base, its quality score goes to 1.
        if seq_read[i] == n_symb:
            quals[i] = 1
            continue
        # if we draw a number less than prob_err for a base, a substitution occurs there.
        if rvals[i] < prob_err[quals[i]]:
            seq_read[i] = random_base(seq_read[i])


class EmpDist:

    FIRST = True
    SECOND = False
    HIGHEST_QUAL = 80
    MAX_DIST_NUMBER = 1.0e6
    CMB_SYMB = '.'
    A_SYMB = 'A'
    C_SYMB = 'C'
    G_SYMB = 'G'
    T_SYMB = 'T'
    N_SYMB = 'N'
    PRIMARY_SYMB = {A_SYMB, C_SYMB, G_SYMB, T_SYMB}
    ALL_SYMB = PRIMARY_SYMB | {CMB_SYMB, N_SYMB}

    # lookup table of probability indexed by quality score
    PROB_ERR = np.apply_along_axis(
        lambda xi: 10.0**(-xi*0.1), 0, np.arange(HIGHEST_QUAL)).tolist()

    # create a map of all combinations of single-symbol knockouts
    # used in random not-symb-si substitutions
    KO_SUBS_LOOKUP = dict([(si, list(PRIMARY_SYMB - set(si))) for si in PRIMARY_SYMB])
    # alternatively, the list of all symbols for uniform random selection
    ALL_SUBS = list(PRIMARY_SYMB)

    @staticmethod
    def create(name, sep_quals=False):
        """
        Instantiate a EmpDist with the specified profile name.
        :param name: empirically derived machine profile
        :param sep_quals: independent quality model per base (A,C,G,T)
        :return: instance of EmpDist
        """
        profile_r1, profile_r2 = get_profile(name)
        return EmpDist(profile_r1, profile_r2, sep_quals)

    def __init__(self, fname_first, fname_second, sep_quals=False):
        """
        :param fname_first: file name of first read profile
        :param fname_second: file name of second read profile
        :param sep_quals: independent quality model per base (A,C,G,T)
        """
        self.sep_quals = sep_quals
        assert not sep_quals, 'Separate base qualities are not currently supported by this python implementation'
        self.qual_dist_first = dict(zip(EmpDist.ALL_SYMB, [[], [], [], [], [], []]))
        self.qual_dist_second = dict(zip(EmpDist.ALL_SYMB, [[], [], [], [], [], []]))
        self.dist_max = {EmpDist.FIRST: 0, EmpDist.SECOND: 0}
        self.init_dist(fname_first, fname_second)

    def init_dist(self, fname_first, fname_second):
        """
        Initialise the per-base_position distribution of quality scores
        :param fname_first: profile for first read
        :param fname_second: profile for second read
        """
        map(_clear_list, self.qual_dist_first.values())
        map(_clear_list, self.qual_dist_second.values())

        with open(fname_first, 'r') as hndl:
            self.read_emp_dist(hndl, True)

        with open(fname_second, 'r') as hndl:
            self.read_emp_dist(hndl, False)

        if not self.sep_quals:
            self.dist_max[EmpDist.FIRST] = len(self.qual_dist_first[self.CMB_SYMB])
            self.dist_max[EmpDist.SECOND] = len(self.qual_dist_second[self.CMB_SYMB])
        else:
            dist_len = np.array([len(self.qual_dist_first[k]) for k in self.PRIMARY_SYMB])
            assert np.all(dist_len == dist_len.max()), \
                'Invalid first profile, not all symbols represented over full range'
            self.dist_max[EmpDist.FIRST] = dist_len.max()

            dist_len = np.array([len(self.qual_dist_second[k]) for k in self.PRIMARY_SYMB])
            assert np.all(dist_len == dist_len.max()), \
                'Invalid second profile, not all symbols represented over full range'
            self.dist_max[EmpDist.SECOND] = dist_len.max()

    def verify_length(self, length, is_first):
        """
        Verify that profile and requested length are agreeable
        :param length: read length
        :param is_first: first or second read
        :return: True -- supported by profile
        """
        assert length <= self.dist_max[is_first], 'Requested length exceeds that of profile'

    def get_read_qual(self, read_len, is_first):
        """
        Read qualities for a given read-length
        :param read_len: length of read to simulate
        :param is_first: first or second read
        :return: simulated qualities
        """
        self.verify_length(read_len, is_first)
        if is_first:
            return self._get_from_dist(self.qual_dist_first[self.CMB_SYMB], read_len)
        else:
            return self._get_from_dist(self.qual_dist_second[self.CMB_SYMB], read_len)

    @staticmethod
    def _get_from_dist(qual_dist_for_symb, read_len):
        """
        Generate simulated quality scores for a given length using an initialised
        distribution. Scores are related to the emporically determined CDFs specified
        at initialisation.
        :param qual_dist_for_symb: combined or separate symbols
        :param read_len: read length to simulate
        :return: simulated quality scores
        """

        # the most time consuming step when simulating quality scores.
        # a list comprehension that uses a iterator over the 2 sequences
        # (the positional Qcdfs and a set of randoms)
        rv_list = Art.RANDINT(1, EmpDist.MAX_DIST_NUMBER+1, size=read_len)
        quals = [qi for qi in imap(EmpDist._lookup_qcdf, qual_dist_for_symb, rv_list)]
        assert len(quals) > 0
        assert len(quals) == read_len
        return quals

    @staticmethod
    def _lookup_qcdf(qcdf, rv):
        """
        Look-up the quality corresponding to a randomly drawn integer on a Empirical Q_CDF.
        :param qcdf: the positional empirical CDF
        :param rv: randomly drawn value
        :return: quality score
        """
        return qcdf[np.searchsorted(qcdf[:, 0], rv), 1]

    def read_emp_dist(self, hndl, is_first):
        """
        Read an empirical distribution from a file.
        :param hndl: open file handle
        :param is_first: first or second read profile
        :return: True -- profile was not empty
        """
        n = 0
        while True:
            line = hndl.readline().strip()

            if not line:
                # end of file
                break
            if len(line) <= 0 or line.startswith('#'):
                # skip empty and comment lines
                continue

            tok = line.split('\t')
            symb, read_pos, values = tok[0], int(tok[1]), np.array(tok[2:], dtype=int)

            # skip lines pertaining to unrequested mode
            if self.sep_quals:
                if symb == self.CMB_SYMB or symb == self.N_SYMB:
                    # requested separate quals but this pertains to combined or N
                    continue
            else:  # if combined
                if symb != self.CMB_SYMB:
                    # requested combined but this pertains to separate
                    continue

            if read_pos != n:
                if read_pos != 0:
                    raise IOError('Error: invalid format in profile at [{0}]'.format(line))
                n = 0

            line = hndl.readline().strip()
            tok = line.split('\t')
            symb, read_pos, counts = tok[0], int(tok[1]), np.array(tok[2:], dtype=int)

            if read_pos != n:
                raise IOError('Error: invalid format in profile at [{0}]'.format(line))

            if len(values) != len(counts):
                raise IOError('Error: invalid format in profile at [{0}]'.format(line))

            dist = np.array([(cc, values[i]) for i, cc in
                             enumerate(np.ceil(counts * EmpDist.MAX_DIST_NUMBER/counts[-1]).astype(int))])

            if dist.size > 0:
                n += 1
                try:
                    if is_first:
                        self.qual_dist_first[symb].append(dist)
                    else:
                        self.qual_dist_second[symb].append(dist)
                except:
                    raise IOError('Error: unexpected base symbol [{0}] linked to distribution'.format(symb))

        return n != 0


class SeqRead:

    def __init__(self, read_len, ins_rate, del_rate, max_num=2, plus_strand=None):
        self.max_num = max_num
        self.read_len = read_len
        self.is_plus_strand = plus_strand
        self.seq_ref = np.zeros(read_len, dtype=np.str)
        self.seq_read = np.zeros(read_len, dtype=np.str)
        self.quals = None
        self.bpos = None
        self.indel = {}
        self.del_rate = del_rate
        self.ins_rate = ins_rate

    def _new_read(self, rlen=None, plus_strand=True):
        """
        Create a new read object ready for simulation.
        :param rlen: a read length other than what was defined when instantiating Art.
        :param plus_strand: True - forward strand, False - reverse strand
        :return: a new read object
        """
        if not rlen:
            return SeqRead(self.read_len, self.ins_rate, self.del_rate, self.max_num, plus_strand=plus_strand)
        else:
            return SeqRead(rlen, self.ins_rate, self.del_rate, self.max_num, plus_strand=plus_strand)

    def __str__(self):
        return 'from {0}...{1}bp created {2}'.format(self.seq_ref[0:10], self.seq_ref.shape[0], self.seq_read)

    def read_record(self, seq_id, desc=''):
        """
        Create a Biopython SeqRecord appropriate for writing to disk and matching the format
        generated by ART_illumina
        :param seq_id: sequence id for read
        :param desc: sequence description
        :return: Bio.SeqRecord
        """
        rec = SeqRecord(
                Seq(self._read_str(), IUPAC.ambiguous_dna),
                id=seq_id,
                description=desc)
        # seems the only means of adding quality scores to a SeqRecord
        rec.letter_annotations['phred_quality'] = self.quals
        return rec

    def _read_desc(self):
        """
        Create a string description for this read, suitable for inclusion if output
        :return: a string description
        """
        return '{0}{1}'.format(self.bpos, 'F' if self.is_plus_strand else 'R')

    @staticmethod
    def read_id(ref_id, n):
        """
        Create an id for this read, based on the mother sequence and an index. This follows ART_illumina
        practice.
        :param ref_id: mother sequence id
        :param n: an index for the read
        :return: a string id for this read
        """
        return '{0}-{1}'.format(ref_id, n)

    def _read_str(self):
        """
        Create a string representation of this read's sequence. This is necessary as internally
        the sequence is handled as a list -- since strings are immutable in Python.
        :return:
        """
        return self.seq_read.tostring()

    # def parse_error(self):
    #     """
    #     When analyzed, sequences are potentially modified by the simulated quality scores.
    #     :return: number of modified bases.
    #     """
    #     assert self.quals, 'Quality scores have not been initialized for the read'
    #     assert len(self.quals) == self.length(), \
    #         "The number of bases is not equal to the number of quality scores!\n" \
    #         "qual size: {0},  read len: {1}".format(len(self.quals), self.length())
    #
    #     for i in xrange(len(self.quals)):
    #         # if we encounter an undefined base, its quality score goes to 1.
    #         if self.seq_read[i] == EmpDist.N_SYMB:
    #             self.quals[i] = 1
    #             continue
    #
    #         # if we draw a number less than prob_err for a base, a substitution occurs there.
    #         if Art.UNIFORM() < EmpDist.PROB_ERR[self.quals[i]]:
    #             sub_ch = Art.random_base(self.seq_read[i])
    #             self.seq_read[i] = sub_ch

    def clear(self):
        """
        Clear the working internal collections.
        """
        self.indel.clear()
        self.seq_ref[:] = 0
        self.seq_read[:] = 0

    def get_indel(self):
        """
        Generate insertion and deletions
        :return: net change in length, i.e. insertion_length - deletion_length
        """
        self.indel.clear()
        ins_len = 0
        del_len = 0

        # deletion
        for i in xrange(len(self.del_rate)-1, -1, -1):
            if self.del_rate[i] >= Art.UNIFORM():
                del_len = i+1
                j = i
                while j >= 0:
                    # invalid deletion positions: 0 or read_len-1
                    pos = Art.RANDINT(0, self.read_len)
                    if pos == 0:
                        continue
                    if pos not in self.indel:
                        self.indel[pos] = '-'
                        j -= 1
                break

        # insertion
        for i in xrange(len(self.ins_rate)-1, -1, -1):
            # ensure that enough unchanged position for mutation
            if self.read_len - del_len - ins_len < i+1:
                continue
            if self.ins_rate[i] >= Art.UNIFORM():
                ins_len = i+1
                j = i
                while j >= 0:
                    pos = Art.RANDINT(0, self.read_len)
                    if pos not in self.indel:
                        self.indel[pos] = Art.random_base()
                        j -= 1
                break

        return ins_len - del_len

    # number of deletions <= number of insertions
    def get_indel_2(self):
        """
        Second method for creating indels. Called in some situations when the first method
        as returned an unusable result.
        :return: net change in length, i.e. insertion_length - deletion_length
        """

        # start over
        self.indel.clear()
        ins_len = 0
        del_len = 0

        for i in xrange(len(self.ins_rate)-1, -1, -1):
            if self.ins_rate[i] >= Art.UNIFORM():
                ins_len = i+1
                j = i
                while j >= 0:
                    pos = Art.RANDINT(0, self.read_len)
                    if pos not in self.indel:
                        self.indel[pos] = Art.random_base()
                        j -= 1
                break

        # deletion
        for i in xrange(len(self.del_rate)-1, -1, -1):
            if del_len == ins_len:
                break

            # ensure that enough unchanged position for mutation
            if self.read_len - del_len - ins_len < i+1:
                continue

            if self.del_rate[i] >= Art.UNIFORM():
                del_len = i+1
                j = i
                while j >= 0:
                    pos = Art.RANDINT(0, self.read_len)
                    if pos == 0:
                        continue
                    if pos not in self.indel:
                        self.indel[pos] = '-'
                        j -= 1
                break

        return ins_len - del_len

    def ref2read(self):
        """
        From the reference (mother) sequence, generating the read's sequence along
        with the indels.
        """
        if len(self.indel) == 0:
            # straight to an result if no indels, where here seq_ref
            # has already been chopped to the read length.
            self.seq_read = self.seq_ref

        else:
            # otherwise, we gotta a little more work to do.
            self.seq_read[:] = 0

            n = 0
            k = 0
            i = 0
            while i < len(self.seq_ref):
                if k not in self.indel:
                    self.seq_read[n] = self.seq_ref[i]
                    n += 1
                    i += 1
                    k += 1
                elif self.indel[k] == '-':
                    # deletion
                    i += 1
                    k += 1
                else:
                    # insertion
                    self.seq_read[n] = self.indel[k]
                    n += 1
                    k += 1

            while k in self.indel:
                self.seq_read[n] = self.indel[k]
                n += 1
                k += 1

    def length(self):
        """
        Return the actual length of the simulation result. This can be shorter than the requested
        length "read_len" due to short templates.
        :return: length of actual simulated sequence
        """
        return self.seq_read.shape[0]


class Art:

    RANDOM_STATE = np.random.RandomState()
    RANDINT = RANDOM_STATE.randint
    UNIFORM = RANDOM_STATE.uniform
    CHOICE = RANDOM_STATE.choice

    # translation table, non-standard bases become N
    COMPLEMENT_TABLE = string.maketrans('acgtumrwsykvhdbnACGTUMRWSYKVHDBN',
                                        'TGCAAnnnnnnnnnnnTGCAANNNNNNNNNNN')

    def __init__(self, read_len, emp_dist, ins_prob, del_prob, max_num=2, seed=None, ref_seq=None):

        # check immediately that read lengths are possible for profile
        emp_dist.verify_length(read_len, True)
        emp_dist.verify_length(read_len, False)
        self.emp_dist = emp_dist

        # initialise random state
        if seed:
            Art.RANDOM_STATE = np.random.RandomState(seed)
            Art.RANDINT = Art.RANDOM_STATE.randint
            Art.UNIFORM = Art.RANDOM_STATE.uniform
            Art.CHOICE = Art.RANDOM_STATE.choice

        # convert immutable string to list
        if ref_seq:
            self.ref_seq = Art.make_mutable(ref_seq)
            self.ref_seq_cmp = list(Art.revcomp(ref_seq))
            self.valid_region = len(ref_seq) - read_len
        else:
            print 'Warning: no reference supplied, calls will have to supply a template'
            self.ref_seq = None
            self.ref_seq_cmp = None

        self.read_len = read_len
        self.max_num = max_num
        self.ins_rate = self._make_rate(ins_prob)
        self.del_rate = self._make_rate(del_prob)

    def _make_rate(self, prob):
        """
        Create the rates for an error type, returning a list of max_num length
        :param prob: probability of an error
        :return: list
        """
        rates = []
        if self.max_num > self.read_len:
            self.max_num = self.read_len
        for i in xrange(1, self.max_num+1):
            rates.append(1 - st.binom.cdf(i, self.read_len, prob))
        return rates

    @staticmethod
    def make_mutable(input_seq):
        """
        Pedantic method to assure that an input sequence is a mutable uppercase collection.
        :param input_seq: input sequence to make mutable
        :return: list of ch
        """
        assert isinstance(input_seq, str), 'Error: supplied sequences must be plain strings.'
        return list(input_seq.upper())

    @staticmethod
    def revcomp(seq):
        """
        Reverse complement a string representation of a sequence. This uses string.translate.
        :param seq: input sequence as a string
        :return: revcomp sequence as a string
        """
        return seq.translate(Art.COMPLEMENT_TABLE)[::-1]

    def _new_read(self, rlen=None, plus_strand=True):
        """
        Create a new read object ready for simulation.
        :param rlen: a read length other than what was defined when instantiating Art.
        :param plus_strand: True - forward strand, False - reverse strand
        :return: a new read object
        """
        if not rlen:
            return SeqRead(self.read_len, self.ins_rate, self.del_rate, self.max_num, plus_strand=plus_strand)
        else:
            return SeqRead(rlen, self.ins_rate, self.del_rate, self.max_num, plus_strand=plus_strand)

    def next_pair_simple_seq(self, template):
        """
        Get a fwd/rev pair of simple error-free reads for a template, where each read is sequenced off the ends.
        :param template: the target tempalte to sequencing fwd/rev
        :return: a dict {'fwd': SeqRead, 'rev': SeqRead}
        """
        return {'fwd': self.next_read_simple_seq(template, True),
                'rev': self.next_read_simple_seq(template, False)}

    def next_read_simple_seq(self, template, plus_strand, qual_val=40):
        """
        Generate a simple error-free read and constant quality values.
        :param template: the target template to sequence
        :param plus_strand: forward: True, reverse: False
        :param qual_val: value of constant quality scores
        :return: SeqRead
        """
        read = self._new_read(plus_strand=plus_strand)
        if len(template) < read.read_len:
            # for templates shorter than the requested length, we sequence its total extent
            read.read_len = len(template)

        if read.is_plus_strand:
            read.seq_ref = np.fromstring(template[:self.read_len], dtype='|S1')
        else:
            rc_temp = Art.revcomp(template)
            read.seq_ref = np.fromstring(rc_temp[:self.read_len], dtype='|S1')
        read.bpos = 0
        read.ref2read()

        # constant quality scores
        read.quals = [qual_val] * read.read_len

        return read

    def next_pair_indel_seq(self, template):
        """
        Get a fwd/rev pair of reads for a template, where each read is sequenced off the ends.
        :param template: the target tempalte to sequencing fwd/rev
        :return: a dict {'fwd': SeqRead, 'rev': SeqRead}
        """
        return {'fwd': self.next_read_indel_seq(template, True),
                'rev': self.next_read_indel_seq(template, False)}

    def next_read_indel_seq(self, template, plus_strand):
        """
        Generate a read off a supplied target template sequence.
        :param template: the target template to sequence
        :param plus_strand: forward: True, reverse: False
        :return: SeqRead
        """
        read = self._new_read(plus_strand=plus_strand)
        mut_temp = Art.make_mutable(template)
        if len(mut_temp) < read.read_len:
            # for templates shorter than the requested length, we sequence its total extent
            read.read_len = len(mut_temp)

        # indels
        slen = read.get_indel()

        # ensure that this read will fit within the extent of the template
        if self.read_len - slen > len(mut_temp):
            slen = read.get_indel_2()

        if read.is_plus_strand:
            read.seq_ref = np.fromiter(mut_temp[:self.read_len - slen], dtype='|S1')
        else:
            rc_temp = Art.revcomp(template)
            read.seq_ref = np.fromstring(rc_temp[:self.read_len - slen], dtype='|S1')

        read.bpos = 0
        read.ref2read()

        # simulated quality scores from profiles
        read.quals = self.emp_dist.get_read_qual(read.length(), read.is_plus_strand)
        # the returned quality scores can spawn sequencing errors
        # read.parse_error()
        parse_error(read.quals, read.seq_read)

        return read

    def next_read_indel_at(self, pos, plus_strand):
        """
        Create a read with an already determined position and direction.
        :param pos: position for read
        :param plus_strand: True = forward, False = reverse
        :return: SeqRead
        """
        read = self._new_read()
        read.is_plus_strand = plus_strand

        # indels
        slen = read.get_indel()

        # ensure that this read will fit within the extent of the reference
        if pos + self.read_len - slen > len(self.ref_seq):
            slen = read.get_indel_2()

        if read.is_plus_strand:
            read.seq_ref = np.fromstring(self.ref_seq[pos: pos + self.read_len - slen], dtype='|S1')
        else:
            read.seq_ref = np.fromstring(self.ref_seq_cmp[pos: pos + self.read_len - slen], dtype='|S1')

        read.bpos = pos
        read.ref2read()

        # simulated quality scores from profiles
        read.quals = self.emp_dist.get_read_qual(read.length(), True)
        # the returned quality scores can spawn sequencing errors
        # read.parse_error()
        parse_error(read.quals, read.seq_read)

        return read

    def next_read_indel(self):
        """
        Create the next SeqRead and its accompanying quality scores. Position and direction are
        determined by uniform random seletion.

        :return: SeqRead
        """
        # random position anywhere in valid range
        pos = Art.RANDINT(0, self.valid_region)

        # is it the forward strand?
        plus_strand = Art.UNIFORM() < 0.5

        return self.next_read_indel_at(pos, plus_strand)

    @staticmethod
    def random_base(excl=None):
        """
        Return a random selection of A,C,G or T. If specified, exclude one of the four.
        :param excl: a base to exclude from the draw
        :return: a random base.
        """
        if not excl:
            return EmpDist.ALL_SUBS[Art.RANDINT(0, 4)]
        else:
            return EmpDist.KO_SUBS_LOOKUP[excl][Art.RANDINT(0, 3)]


if __name__ == '__main__':

    from Bio import SeqIO
    import argparse
    import math
    import numpy as np

    parser = argparse.ArgumentParser(description='Generate Illumina reads')
    parser.add_argument('-S', '--seed', type=int, default=None, help='Random seed')
    parser.add_argument('--profile1', help='ART sequencer profile for R1', required=True)
    parser.add_argument('--profile2', help='ART sequencer profile for R2', required=True)
    parser.add_argument('-l', '--read-length', type=int, help='Read length', required=True)
    parser.add_argument('-X', '--xfold', type=float, help='Depth of coverage')
    parser.add_argument('-N', '--num-reads', type=int, help='Number of reads')
    parser.add_argument('--ins-rate', type=float, default=0.00009, help='Insert rate')
    parser.add_argument('--del-rate', type=float, default=0.00011, help='Deletion rate')
    parser.add_argument('fasta', help='Reference fasta')
    parser.add_argument('outbase', help='Output base name')
    args = parser.parse_args()

    if args.xfold and args.num_reads:
        raise RuntimeError('xfold and num-reads are mutually exclusive options')

    with open('{0}.r1.fq'.format(args.outbase), 'w', buffering=262144) as r1_h, \
            open('{0}.r2.fq'.format(args.outbase), 'w', buffering=262144) as r2_h:

        for input_record in SeqIO.parse(args.fasta, 'fasta'):

            # ref to string
            ref_seq = str(input_record.seq)

            # empirical distribution from files
            emp_dist = EmpDist(args.profile1, args.profile2)

            # init Art
            art = Art(args.read_length, emp_dist,
                      args.ins_rate, args.del_rate, seed=args.seed)

            if args.xfold:
                num_seq = int(math.ceil(len(art.ref_seq) / args.read_length * args.xfold))
            else:
                num_seq = args.num_reads

            print 'Generating {0} reads for {1}'.format(num_seq, input_record.id)

            print_rate = int(num_seq*100./10)

            for n in xrange(num_seq):

                ins_len = None
                while True:
                    ins_len = int(np.ceil(np.random.normal(500, 50)))
                    if ins_len > 200:
                        break

                # pick a random position on the chromosome, but we're lazy and don't
                # handle the edge case of crossing the origin
                pos = Art.RANDINT(0, len(ref_seq)-ins_len)

                # get next read and quals
                pair = art.next_pair_indel_seq(list(ref_seq[pos: pos + ins_len]))

                # create file records
                SeqIO.write(pair['fwd'].read_record(SeqRead.read_id(input_record.id, n)), r1_h, 'fastq')
                SeqIO.write(pair['rev'].read_record(SeqRead.read_id(input_record.id, n)), r2_h, 'fastq')

                if ((n+1)*100) % print_rate == 0:
                    print '\tWrote {0} pairs'.format(n+1)
            break