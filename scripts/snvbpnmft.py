#!/usr/bin/env python
from __future__ import division
#
# wrapper script to: 
# (1) compute SNVs using lofreq*
# (2) compute a variational Bayes Poisson non-negative matrix factorization
# (3) do phylogenetic inference on the strain genotype matrix
#

import sys
import re
import os

lofreq = "lofreq"
num_strains = 0
alpha_index = {'A':0,'C':1,'G':2,'T':3}
ref_alleles = list()
snv_alleles = list()

def parse_bpnmf(bpnmf_filename):
    bpnmf_file = open(bpnmf_filename)
    global num_strains
    # init 2D array of tip partials
    tip_partials = [[[0 for x in range(num_sites)] for s in range(num_strains)] for x in range(len(alpha_index))]

    ll = -2 # skip the first line (csv header)
    for line in bpnmf_file:
        if line.startswith("#"):
            continue 
        ll += 1
        if ll < 0:
            continue
        d = line.split(",")
        for s in range(num_strains):
            begin = num_samples * num_strains + 1 + num_sites * s
            end = begin + num_sites
            for j in range(begin,end):
                tip_partials[alpha_index[ref_alleles[j-begin]]][s][j-begin] += 1-float(d[j])
                tip_partials[alpha_index[snv_alleles[j-begin]]][s][j-begin] += float(d[j])

        # normalize to a tip partial distribution
        for s in range(num_strains):
            for j in range(num_sites):
                m = 0
                for i in range(len(alpha_index)):
                    m = m + tip_partials[i][s][j]
                for i in range(len(alpha_index)):
                    tip_partials[i][s][j] = tip_partials[i][s][j] / m

    return tip_partials


def run_bpnmf(num_strains):
    snv_filename = os.path.join(out_dir, "snv_file.data.R")
    snv_file = open(snv_filename, "w")
    snv_file.write("U<-" + str(num_sites) + "\n")  # number of sites
    snv_file.write("totalsites<-" + str(num_sites) + "\n")  # number of sites
    snv_file.write("T<-" + str(num_samples) + "\n")  # number of time points
    snv_file.write("S<-" + str(num_strains) + "\n")  # number of time points
    snv_file.write("maxdepth<-500" + "\n")  # maximum depth of cov, to constrain uniform prior
    obs = "notz <- c("
    muts = "noty <- c("
    siteids = "#siteids <- c("
    refa = "#refalleles <- c("
    vara = "#varalleles <- c("
    sepchar = ""
    for chromo in variant_sites:
        for site in sorted(variant_sites[chromo].keys()):
            siteids = siteids + sepchar + str(site)
            refa = refa + sepchar + str(variant_sites[chromo][site][0])
            vara = vara + sepchar + str(variant_sites[chromo][site][1])
            ref_alleles.append(variant_sites[chromo][site][0])
            snv_alleles.append(variant_sites[chromo][site][1])
            for i in range(num_samples):
                obs = obs + sepchar + str(depths[i][chromo][site][0])
                muts = muts + sepchar + str(depths[i][chromo][site][1])
                sepchar = ","

    snv_file.write(obs+")\n")
    snv_file.write(muts+")\n")
    snv_file.write(refa+")\n")
    snv_file.write(vara+")\n")
    snv_file.write(siteids+")\n")
    snv_file.close()


    ##
    # run the Poisson NMF
    #
    bpnmf_filename = os.path.join(out_dir, "decon." + str(num_strains) + ".csv")
    diag_filename =  os.path.join(out_dir, "diag." + str(num_strains) + ".csv")
    bpnmf_cmd = "genotypes3 variational output_samples=100 tol_rel_obj=0.001 iter=25000 algorithm=meanfield data file=" + snv_filename + " output file=" + bpnmf_filename + " diagnostic_file=" + diag_filename
    os.system(bpnmf_cmd)
    #os.remove(snv_filename)


# parse the command-line
if len(sys.argv)<5:
    print "Usage: snvbpnmft.py <output directory> <reference fasta> <sample 1 bam> <sample 2 bam> .. [sample N bam]";
    sys.exit(-1)
out_dir = sys.argv[1]
ref_fa = sys.argv[2]
num_samples = len(sys.argv) - 3

depths = dict()
variant_sites = dict()
found = dict()

##
# make variant calls for each input bam
# parse the VCF and store calls in snvs dict
#
for i in range(num_samples):
    found[i] = dict()
    depths[i] = dict()
    cur_vcf = os.path.join(out_dir, str(i) + ".vcf")
    lofreq_cmd = lofreq + " call " + " -C 2 -f " + ref_fa + " -o tmp.vcf " + sys.argv[i+3] 
    print lofreq_cmd
    os.system(lofreq_cmd)
    filter_cmd = lofreq + " filter -i tmp.vcf -B 15 -Q 60 -o " + cur_vcf 
    print filter_cmd
    os.system(filter_cmd)
    os.remove("tmp.vcf")
    cur_pileup = os.path.join(out_dir, str(i) + ".pileup")
    pileup_cmd = "samtools mpileup -f " + ref_fa + " " + sys.argv[i+3] + " > " + cur_pileup
    print pileup_cmd
    os.system(pileup_cmd)
    vcf_file = open(cur_vcf)
    for line in vcf_file:
        if line.startswith("#"):
            continue
        line.rstrip()
        d = line.split("\t")
        if not d[6].startswith("PASS"):
            continue    # didnt pass filters
        mo = re.search('DP4=.+,.+,(.+),(.+)', d[7])
        mo1 = int(mo.group(1))
        mo2 = int(mo.group(2))
        if(mo1 < 1 or mo2 < 1):
            continue    # variant not observed on both strands. unreliable.
        m = re.search('DP=(.+);AF=(.+);SB', d[7])
        vac = round(float(m.group(1)) * float(m.group(2)))

        chromo = d[0]
        site = int(d[1])

        if not chromo in depths[i]:
            depths[i][chromo] = dict()
            found[i][chromo] = dict()
        if not chromo in variant_sites:
            variant_sites[chromo] = dict()
        depths[i][chromo][site] = [m.group(1), int(vac)]
        variant_sites[chromo][site]=[d[3],d[4]] # store the ref & variant allele
        found[i][chromo][site] = 1

for i in range(num_samples):
    # get the depths for samples without a variant allele at the site
    cur_pileup = os.path.join(out_dir, str(i) + ".pileup")
    pileup_file = open(cur_pileup)
    for line in pileup_file:
        d = line.split("\t")
        chromo = d[0]
        if not chromo in depths[i]:
            depths[i][chromo] = dict()
        site = int(d[1])
        if site in variant_sites[chromo] and not site in found[i][chromo]:
            depths[i][chromo][site] = [d[3],0]
    os.remove(cur_pileup)
    
##
# write out a file with SNVs and sample count for Bayesian PNMF
#
num_sites = 0
for chromo in variant_sites:
    num_sites += len(variant_sites[chromo])
min_strains = 4
max_strains = 4
num_repeats = 1
best_ELBO = -9999999999999
best_strains = 0
S_ELBOS = [None]*(max_strains+1)
bpnmf_filename = ""
for S in range(min_strains,max_strains+1):
    for r in range(1,num_repeats+1):
        run_bpnmf(S)
        diag_file = open("diag."+str(S)+".csv")
        for line in diag_file:
            if line.startswith("#"):
                continue
            d = line.split(",")
            cur_elbo = float(d[2])
            if(cur_elbo>best_ELBO):
                best_ELBO=cur_elbo
                best_strains = S
                bpnmf_filename = os.path.join(out_dir, "decon." + str(S) + ".csv")
            if(S_ELBOS[S] == None or cur_elbo>S_ELBOS[S]):
                S_ELBOS[S] = cur_elbo

print "Best strains is " + str(best_strains) + ", ELBO " + str(best_ELBO)
bpnmf_filename = os.path.join(out_dir, "decon.csv")
os.system("mv " + os.path.join(out_dir, "decon." + str(best_strains) + ".csv") + " " + bpnmf_filename)
for s in range(min_strains,max_strains+1):
    print str(s) + " strains ELBO " + str(S_ELBOS[s])

num_strains = best_strains

##
# summarize the tip partials and create a BEAST XML
#
beast_filename = os.path.join(out_dir, "beast.xml")
bpnmf_file = open(bpnmf_filename)
beast_file = open(beast_filename, "w")

# init 2D array of tip partials
tip_partials = parse_bpnmf(bpnmf_filename)

beast_file.write( """<?xml version="1.0" standalone="yes"?>

<!-- Generated by snvbpnmft.py (c) Aaron Darling                                 -->
<beast>

	<!-- The list of taxa to be analysed (can also include dates/ages).          -->
	<taxa id="taxa">
""")

for s in range(num_strains):
	beast_file.write("<taxon id=\"" + str(s).zfill(5) + "\"/>\n");

beast_file.write( """
	</taxa>

	<!-- The partially resolved sequence alignment (each sequence refers to a taxon above).         -->
	<partiallyresolvedpatterns id=\"patterns\" dataType=\"nucleotide\">
""")

# write to xml
for s in range(num_strains):
    beast_file.write("\t\t<partiallyresolvedsequence>\n")
    for i in range(len(alpha_index)):
        beast_file.write("\t\t\t<parameter value=\"")
        beast_file.write(" ".join(map(str,tip_partials[i][s])))
        beast_file.write("\"/>\n")
    beast_file.write("\t\t\t<taxon idref=\"" + str(s).zfill(5) + "\"/>\n\t\t</partiallyresolvedsequence>\n");

beast_file.write( """
	</partiallyresolvedpatterns>

	<!-- A prior assumption that the population size has remained constant       -->
	<!-- throughout the time spanned by the genealogy.                           -->
	<constantSize id="constant" units="years">
		<populationSize>
			<parameter id="constant.popSize" value="0.4" lower="0.0"/>
		</populationSize>
	</constantSize>

	<!-- Generate a random starting tree under the coalescent process            -->
	<coalescentSimulator id="startingTree">
		<taxa idref="taxa"/>
		<constantSize idref="constant"/>
	</coalescentSimulator>

	<!-- Generate a tree model                                                   -->
	<treeModel id="treeModel">
		<coalescentTree idref="startingTree"/>
		<rootHeight>
			<parameter id="treeModel.rootHeight"/>
		</rootHeight>
		<nodeHeights internalNodes="true">
			<parameter id="treeModel.internalNodeHeights"/>
		</nodeHeights>
		<nodeHeights internalNodes="true" rootNode="true">
			<parameter id="treeModel.allInternalNodeHeights"/>
		</nodeHeights>
	</treeModel>

	<!-- Generate a coalescent likelihood                                        -->
	<coalescentLikelihood id="coalescent">
		<model>
			<constantSize idref="constant"/>
		</model>
		<populationTree>
			<treeModel idref="treeModel"/>
		</populationTree>
	</coalescentLikelihood>

	<!-- The strict clock (Uniform rates across branches)                        -->
	<strictClockBranchRates id="branchRates">
		<rate>
			<parameter id="clock.rate" value="1.0"/>
		</rate>
	</strictClockBranchRates>

	<!-- The HKY substitution model (Hasegawa, Kishino & Yano, 1985)             -->
	<HKYModel id="hky">
		<frequencies>
			<frequencyModel dataType="nucleotide">
				<frequencies>
					<parameter id="frequencies" value="0.25 0.25 0.25 0.25"/>
				</frequencies>
			</frequencyModel>
		</frequencies>
		<kappa>
			<parameter id="kappa" value="2.0" lower="0.0"/>
		</kappa>
	</HKYModel>

	<!-- site model                                                              -->
	<siteModel id="siteModel">
		<substitutionModel>
			<HKYModel idref="hky"/>
		</substitutionModel>
	</siteModel>

	<!-- Likelihood for tree given sequence data                                 -->
	<treeLikelihood id="treeLikelihood" useAmbiguities="false">
		<patterns idref="patterns"/>
		<treeModel idref="treeModel"/>
		<siteModel idref="siteModel"/>
		<strictClockBranchRates idref="branchRates"/>
	</treeLikelihood>

	<!-- Define operators                                                        -->
	<operators id="operators" optimizationSchedule="default">
		<scaleOperator scaleFactor="0.75" weight="0.1">
			<parameter idref="kappa"/>
		</scaleOperator>
		<deltaExchange delta="0.01" weight="0.1">
			<parameter idref="frequencies"/>
		</deltaExchange>
		<subtreeSlide size="0.04" gaussian="true" weight="15">
			<treeModel idref="treeModel"/>
		</subtreeSlide>
		<narrowExchange weight="15">
			<treeModel idref="treeModel"/>
		</narrowExchange>
		<wideExchange weight="3">
			<treeModel idref="treeModel"/>
		</wideExchange>
		<wilsonBalding weight="3">
			<treeModel idref="treeModel"/>
		</wilsonBalding>
		<scaleOperator scaleFactor="0.75" weight="3">
			<parameter idref="treeModel.rootHeight"/>
		</scaleOperator>
		<uniformOperator weight="30">
			<parameter idref="treeModel.internalNodeHeights"/>
		</uniformOperator>
		<scaleOperator scaleFactor="0.75" weight="3">
			<parameter idref="constant.popSize"/>
		</scaleOperator>
		<upDownOperator scaleFactor="0.75" weight="3">
			<up>
			</up>
			<down>
				<parameter idref="treeModel.allInternalNodeHeights"/>
			</down>
		</upDownOperator>
	</operators>

	<!-- Define MCMC                                                             -->
	<mcmc id="mcmc" chainLength="5000000" autoOptimize="true" operatorAnalysis=""" + "\"" + os.path.join(out_dir,"aln.ops") + "\">" + """
		<posterior id="posterior">
			<prior id="prior">
				<logNormalPrior mean="1.0" stdev="1.25" offset="0.0" meanInRealSpace="false">
					<parameter idref="kappa"/>
				</logNormalPrior>
				<uniformPrior lower="0.0" upper="1.0">
					<parameter idref="frequencies"/>
				</uniformPrior>
				<uniformPrior lower="0.0" upper="10.0">
					<parameter idref="treeModel.rootHeight"/>
				</uniformPrior>
				<oneOnXPrior>
					<parameter idref="constant.popSize"/>
				</oneOnXPrior>
				<coalescentLikelihood idref="coalescent"/>
			</prior>
			<likelihood id="likelihood">
				<treeLikelihood idref="treeLikelihood"/>
			</likelihood>
		</posterior>
		<operators idref="operators"/>

		<!-- write log to screen                                                     -->
		<log id="screenLog" logEvery="1000">
			<column label="Posterior" dp="4" width="12">
				<posterior idref="posterior"/>
			</column>
			<column label="Prior" dp="4" width="12">
				<prior idref="prior"/>
			</column>
			<column label="Likelihood" dp="4" width="12">
				<likelihood idref="likelihood"/>
			</column>
			<column label="rootHeight" sf="6" width="12">
				<parameter idref="treeModel.rootHeight"/>
			</column>
			<column label="clock.rate" sf="6" width="12">
				<parameter idref="clock.rate"/>
			</column>
		</log>

		<!-- write log to file                                                       -->
		<log id="fileLog" logEvery="1000" fileName=""" + "\"" + os.path.join(out_dir,"aln.log") + "\"" + """ overwrite="false">
			<posterior idref="posterior"/>
			<prior idref="prior"/>
			<likelihood idref="likelihood"/>
			<parameter idref="treeModel.rootHeight"/>
			<parameter idref="constant.popSize"/>
			<parameter idref="kappa"/>
			<parameter idref="frequencies"/>
			<parameter idref="clock.rate"/>
			<treeLikelihood idref="treeLikelihood"/>
			<coalescentLikelihood idref="coalescent"/>
		</log>

		<!-- write tree log to file                                                  -->
		<logTree id="treeFileLog" logEvery="1000" nexusFormat="true" fileName=""" + "\"" + os.path.join(out_dir,"aln.trees") + "\"" + """ sortTranslationTable="true">
			<treeModel idref="treeModel"/>
			<trait name="rate" tag="rate">
				<strictClockBranchRates idref="branchRates"/>
			</trait>
			<posterior idref="posterior"/>
		</logTree>
	</mcmc>
	<report>
		<property name="timer">
			<mcmc idref="mcmc"/>
		</property>
	</report>
</beast>
""");

beast_file.close()

ra_index = {0:'A',1:'C',2:'G',3:'T'}
strains_file = open("strains.fa", "w")
for s in range(num_strains):
    strains_file.write("strain_" + str(s) + "\n")
    cur_seq = ""
    for j in range(num_sites):
        amax = "-"
        for i in range(len(alpha_index)):
            if tip_partials[i][s][j] > 0.8:
                amax = ra_index[i]
        cur_seq += amax
    strains_file.write(cur_seq + "\n")

