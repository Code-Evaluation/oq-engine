# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2023, GEM Foundation
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake.  If not, see <http://www.gnu.org/licenses/>.

import logging
import numpy
from openquake.baselib import parallel, general
from openquake.hazardlib.calc.mrd import calc_mean_rate_dist
from openquake.hazardlib import contexts, cross_correlation as cc


class Input(object):
    # here just to give a sensible .weight attribute
    def __init__(self, ctx, cmaker, N):
        self.ctx = ctx
        self.cmaker = cmaker
        self.N = N
        self.weight = len(ctx)


def compute_mrd(inp, crosscorr, imt1, imt2,
                meabins, sigbins, monitor):
    """
    :param inp: an Input object (contexts, contextm maker, num_sites)
    :param N: the total number of sites
    :param cmaker: a ContextMaker instance
    :param crosscorr: cross correlation model
    :param str imt1: the first Intensity Measure Type
    :param str imt1: the second Intensity Measure Type
    :param meabins: bins for the means
    :param sigbins: bins for the sigmas
    :returns: 4D-matrix with shape (L1, L1, N, G)
    """
    mrd = calc_mean_rate_dist(inp.ctx, inp.N, inp.cmaker, crosscorr,
                              imt1, imt2, meabins, sigbins)
    return {g: mrd[:, :, :, i] for i, g in enumerate(inp.cmaker.gidx)}


def combine_mrds(acc, rlzs_by_g):
    rlzs = rlzs_by_g['rlzs']
    weig = rlzs_by_g['weight']
    g = next(iter(acc))  # first key
    out = numpy.zeros(acc[g].shape)  # shape (L1, L1, N)
    for g in acc:
        value = acc[g]
        for rlz in rlzs[g]:
            out += weig[rlz] * value
    return out


def main(dstore, imt1, imt2, cross_correlation, seed, meabins, sigbins):
    """
    :param dstore: datastore with the classical calculation

    NB: this is meant to work only for parametric ruptures!
    """
    crosscorr = getattr(cc, cross_correlation)()
    oq = dstore['oqparam']
    N = len(dstore['sitecol'])
    L1 = oq.imtls.size // len(oq.imtls) - 1
    if L1 > 24:
        logging.warning('There are many intensity levels (%d), the '
                        'calculation can be pretty slow', L1 + 1)
    assert N <= 10, 'Too many sites: %d' % N
    cmakers = contexts.read_cmakers(dstore)
    ctx_by_grp = contexts.read_ctx_by_grp(dstore)
    n = sum(len(ctx) for ctx in ctx_by_grp.values())
    logging.info('Read {:_d} contexts'.format(n))
    blocksize = numpy.ceil(n / oq.concurrent_tasks)
    dstore.swmr_on()
    smap = parallel.Starmap(compute_mrd, h5=dstore)
    for grp_id, ctx in ctx_by_grp.items():
        cmaker = cmakers[grp_id]
        for slc in general.gen_slices(0, len(ctx), blocksize):
            smap.submit((Input(ctx[slc], cmaker, N), crosscorr, imt1, imt2,
                         meabins, sigbins))
    acc = smap.reduce()
    mrd = dstore.create_dset('mrd', float, (L1, L1, N))
    mrd[:] = combine_mrds(acc, dstore['rlzs_by_g'][:])
