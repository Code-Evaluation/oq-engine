# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2013-2022 GEM Foundation
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
# along with OpenQuake. If not, see <http://www.gnu.org/licenses/>.

"""
Module exports :class:`KaleEtAl2015Turkey`
               :class:`KaleEtAl2015Iran`.
"""
import numpy as np
from openquake.hazardlib.gsim.base import GMPE, CoeffsTable
from openquake.hazardlib import const
from openquake.hazardlib.imt import PGA, PGV, SA


def _compute_anelestic_attenuation_term(C, ctx):
    """
    Compute and return anelastic attenuation term in equation 5,
    page 970.
    """
    f_aat = np.zeros_like(ctx.rjb)
    idx = ctx.rjb > 80.0
    f_aat[idx] = C["b10"] * (ctx.rjb[idx] - 80.0)
    return f_aat


def _compute_faulting_style_term(C, rake):
    """
    Compute and return style-of-faulting term in equation 4,
    page 970.
    """
    Fn = float(rake > -135.0 and rake < -45.0)
    Fr = float(rake > 45.0 and rake < 135.0)

    return C['b8'] * Fn + C['b9'] * Fr


def _compute_geometric_decay_term(c1, C, mag, ctx):
    """
    Compute and return geometric decay term in equation 3,
    page 970.
    """
    return (
        (C['b4'] + C['b5'] * (mag - c1)) *
        np.log(np.sqrt(ctx.rjb ** 2.0 + C['b6'] ** 2.0)))


def _compute_magnitude_scaling_term(c1, C, mag):
    """
    Compute and return magnitude scaling term in equation 2,
    page 970.
    """
    if mag <= c1:
        return C['b1'] + C['b2'] * (mag - c1) + C['b3'] * (8.5 - mag) ** 2
    else:
        return C['b1'] + C['b7'] * (mag - c1) + C['b3'] * (8.5 - mag) ** 2


def _compute_mean(CONSTS, C, mag, ctx, rake):
    """
    Compute and return mean value without site conditions,
    that is equations 2-5, page 970.
    """
    c1 = CONSTS['c1']
    mean = (
        _compute_magnitude_scaling_term(c1, C, mag) +
        _compute_geometric_decay_term(c1, C, mag, ctx) +
        _compute_faulting_style_term(C, rake) +
        _compute_anelestic_attenuation_term(C, ctx))

    return mean


def _compute_non_linear_term(CONSTS, C, pga_only, ctx):
    """
    Compute non-linear term, equation 6, page 970.
    """
    Vref = CONSTS['Vref']
    Vcon = CONSTS['Vcon']
    c = CONSTS['c']
    n = CONSTS['n']
    lnS = np.zeros_like(ctx.vs30)

    # equation (6a)
    idx = ctx.vs30 < Vref
    lnS[idx] = (
        C['sb1'] * np.log(ctx.vs30[idx] / Vref) +
        C['sb2'] * np.log(
            (pga_only[idx] + c * (ctx.vs30[idx] / Vref) ** n) /
            ((pga_only[idx] + c) * (ctx.vs30[idx] / Vref) ** n)))

    # equation (6b)
    idx = ctx.vs30 >= Vref
    new_sites = ctx.vs30[idx]
    new_sites[new_sites > Vcon] = Vcon
    lnS[idx] = C['sb1'] * np.log(new_sites / Vref)

    return lnS


def _compute_weight_std(C, mag):
    """
    Common part of equations 8 and 9, page 971.
    """
    if mag < 6.0:
        return C['a1']
    elif mag >= 6.0 and mag < 6.5:
        return C['a1'] + (C['a2'] - C['a1']) * ((mag - 6.0) / 0.5)
    else:
        return C['a2']


class KaleEtAl2015Turkey(GMPE):
    """
    Implements GMPE developed by O. Kale, S. Akkar, A. Ansari and H. Hamzehloo
    as published in "A ground-motion predictive model for Iran and Turkey for
    horizontal PGA, PGV and 5%-damped response spectrum: Investigation of
    possible regional effects", Bulletin of the Seismological Society of
    America (2015), 105(2A): 963 - 980. The class implements the equations for
    Joyner-Boore distance and based on manuscript provided by the original
    authors.

    Version calibrated for the Turkey case
    """
    #: The supported tectonic region type is active shallow crust.
    DEFINED_FOR_TECTONIC_REGION_TYPE = const.TRT.ACTIVE_SHALLOW_CRUST

    #: The supported intensity measure types are PGA, PGV, and SA, see table
    #: 5, page 973
    DEFINED_FOR_INTENSITY_MEASURE_TYPES = {PGA, PGV, SA}

    #: The supported intensity measure component is 'geometric mean', see
    #: section 'Functional Form of the GMPEs and Regression Analyses', page 970
    DEFINED_FOR_INTENSITY_MEASURE_COMPONENT = const.IMC.AVERAGE_HORIZONTAL

    #: The supported standard deviations are total, inter and intra event, see
    #: table 3 and equations 8 & 9, pages 972 and 971
    DEFINED_FOR_STANDARD_DEVIATION_TYPES = {
        const.StdDev.TOTAL, const.StdDev.INTER_EVENT, const.StdDev.INTRA_EVENT}

    #: The required site parameter is vs30, see equation 6, page 970.
    REQUIRES_SITES_PARAMETERS = {'vs30'}

    #: The required rupture parameters are rake and magnitude, see equations
    #: 2 and 4, page 970.
    REQUIRES_RUPTURE_PARAMETERS = {'rake', 'mag'}

    #: The required distance parameter is 'Joyner-Boore' distance, see
    #: equation 3, page 970.
    REQUIRES_DISTANCES = {'rjb'}

    def compute(self, ctx, imts, mean, sig, tau, phi):
        """
        See :meth:`superclass method
        <.base.GroundShakingIntensityModel.compute>`
        for spec of input and result values.

        Implement equation 1, page 970.
        """
        # compute median PGA on rock, needed to compute non-linear site
        # amplification
        C_pga = self.COEFFS[PGA()]
        median_pga = np.exp(
            _compute_mean(self.CONSTS, C_pga, ctx.mag, ctx, ctx.rake))
        for m, imt in enumerate(imts):
            # compute mean value by adding nonlinear site amplification terms
            C = self.COEFFS[imt]
            mean[m] = (
                _compute_mean(self.CONSTS, C, ctx.mag, ctx, ctx.rake) +
                _compute_non_linear_term(self.CONSTS, C, median_pga, ctx))

            # Return standard deviations as defined in p. 971.
            weight = _compute_weight_std(C, ctx.mag)
            std_intra = weight * C["sd1"]
            std_inter = weight * C["sd2"]
            sig[m] = np.sqrt(std_intra ** 2. + std_inter ** 2.)
            tau[m] = std_inter
            phi[m] = std_intra

    #: Coefficient tables obtained by joining tables 2, 3, 4, 5
    #: and electronic supplementary
    COEFFS = CoeffsTable(sa_damping=5, table="""\
    IMT              b1         b2            b3            b4         b5       b6          b7            b8            b9          b10          a1         a2         sd1         sd2           sb1           sb2
    pga         1.74221      0.193      -0.07049      -1.18164      0.170      8.0      -0.354      -0.01329      -0.09158      -0.00156      0.570      0.450      1.0521      0.7203      -0.41997      -0.28846
    pgv         5.58266      0.193      -0.13822      -0.94043      0.170      8.0      -0.354      -0.17037      -0.08609      -0.00052      0.560      0.460      1.0449      0.6452      -0.72057      -0.19688
    0.010       1.75746      0.193      -0.06981      -1.18362      0.170      8.0      -0.354      -0.01349      -0.09158      -0.00156      0.574      0.453      1.0444      0.7150      -0.41729      -0.28685
    0.020       1.78825      0.193      -0.07058      -1.18653      0.170      8.0      -0.354      -0.01189      -0.09158      -0.00160      0.577      0.455      1.0424      0.7137      -0.39998      -0.28241
    0.030       1.87916      0.193      -0.06976      -1.19699      0.170      8.0      -0.354      -0.00748      -0.09158      -0.00170      0.581      0.458      1.0459      0.7113      -0.34799      -0.26842
    0.040       2.00393      0.193      -0.06732      -1.21315      0.170      8.0      -0.354       0.00788      -0.09158      -0.00182      0.584      0.460      1.0557      0.7155      -0.27572      -0.24759
    0.050       2.16076      0.193      -0.06226      -1.24101      0.170      8.0      -0.354       0.03907      -0.09158      -0.00197      0.588      0.463      1.0609      0.7166      -0.21231      -0.22385
    0.075       2.52625      0.193      -0.05082      -1.30390      0.170      8.0      -0.354       0.08131      -0.09158      -0.00235      0.597      0.469      1.0692      0.7677      -0.13909      -0.17798
    0.100       2.72364      0.193      -0.05217      -1.32996      0.170      8.0      -0.354       0.10000      -0.09158      -0.00267      0.606      0.475      1.0429      0.7735      -0.26492      -0.28832
    0.110       2.79879      0.193      -0.05423      -1.33631      0.170      8.0      -0.354       0.10000      -0.09158      -0.00277      0.610      0.478      1.0324      0.7871      -0.31346      -0.31798
    0.120       2.87745      0.193      -0.05676      -1.34267      0.170      8.0      -0.354       0.10000      -0.09158      -0.00285      0.613      0.480      1.0208      0.7783      -0.36002      -0.34246
    0.130       2.89671      0.193      -0.05922      -1.33525      0.170      8.0      -0.354       0.09500      -0.09158      -0.00291      0.617      0.483      1.0216      0.7598      -0.40424      -0.36297
    0.140       2.91231      0.193      -0.06162      -1.32731      0.170      8.0      -0.354       0.08169      -0.09158      -0.00295      0.621      0.485      1.0194      0.7517      -0.44592      -0.38036
    0.150       2.91835      0.193      -0.06397      -1.31888      0.170      8.0      -0.354       0.06727      -0.09158      -0.00296      0.624      0.488      1.0063      0.7442      -0.48496      -0.39525
    0.160       2.92057      0.193      -0.06626      -1.30999      0.170      8.0      -0.354       0.05460      -0.09158      -0.00295      0.628      0.490      0.9980      0.7380      -0.52137      -0.40811
    0.170       2.91550      0.193      -0.06850      -1.30069      0.170      8.0      -0.354       0.04338      -0.09158      -0.00292      0.631      0.493      0.9896      0.7484      -0.55520      -0.41930
    0.180       2.90336      0.193      -0.07069      -1.29102      0.170      8.0      -0.354       0.03335      -0.09158      -0.00288      0.635      0.495      0.9854      0.7472      -0.58656      -0.42911
    0.190       2.88447      0.193      -0.07284      -1.28102      0.170      8.0      -0.354       0.02435      -0.09158      -0.00282      0.639      0.498      0.9801      0.7310      -0.61558      -0.43774
    0.200       2.85623      0.193      -0.07494      -1.27072      0.170      8.0      -0.354       0.01620      -0.09158      -0.00275      0.642      0.500      0.9781      0.7213      -0.64239      -0.44574
    0.220       2.78548      0.193      -0.07902      -1.24942      0.170      8.0      -0.354       0.00201      -0.09158      -0.00258      0.649      0.505      0.9712      0.7120      -0.69002      -0.45499
    0.240       2.70779      0.193      -0.08294      -1.22742      0.170      8.0      -0.354      -0.00996      -0.09158      -0.00240      0.657      0.510      0.9699      0.6901      -0.73062      -0.45939
    0.260       2.62349      0.193      -0.08672      -1.20502      0.170      8.0      -0.354      -0.02021      -0.09158      -0.00226      0.664      0.515      0.9611      0.6732      -0.76530      -0.45988
    0.280       2.53452      0.193      -0.09036      -1.18250      0.170      8.0      -0.354      -0.02913      -0.09158      -0.00215      0.671      0.520      0.9466      0.6714      -0.79499      -0.45739
    0.300       2.44252      0.193      -0.09387      -1.16008      0.170      8.0      -0.354      -0.03697      -0.09158      -0.00204      0.678      0.525      0.9407      0.6547      -0.82052      -0.45287
    0.320       2.34886      0.193      -0.09726      -1.13796      0.170      8.0      -0.354      -0.04395      -0.09158      -0.00194      0.686      0.530      0.9515      0.6515      -0.84256      -0.44255
    0.340       2.25469      0.193      -0.10054      -1.11632      0.170      8.0      -0.354      -0.05021      -0.09158      -0.00185      0.693      0.535      0.9448      0.6490      -0.86167      -0.43399
    0.360       2.16096      0.193      -0.10372      -1.09527      0.170      8.0      -0.354      -0.05588      -0.09158      -0.00177      0.700      0.540      0.9344      0.6545      -0.87832      -0.42592
    0.380       2.06843      0.193      -0.10679      -1.07492      0.170      8.0      -0.354      -0.06106      -0.09158      -0.00168      0.700      0.545      0.9406      0.6504      -0.89288      -0.41829
    0.400       1.97772      0.193      -0.10977      -1.05535      0.170      8.0      -0.354      -0.06582      -0.09158      -0.00161      0.700      0.550      0.9430      0.6413      -0.90568      -0.41105
    0.420       1.88929      0.193      -0.11266      -1.03659      0.170      8.0      -0.354      -0.07021      -0.09158      -0.00153      0.695      0.550      0.9449      0.6316      -0.91697      -0.40417
    0.440       1.80350      0.193      -0.11547      -1.01869      0.170      8.0      -0.354      -0.07430      -0.08070      -0.00146      0.689      0.550      0.9444      0.6357      -0.92698      -0.39760
    0.460       1.72061      0.193      -0.11819      -1.00165      0.170      8.0      -0.354      -0.07813      -0.05565      -0.00140      0.684      0.550      0.9438      0.6483      -0.93589      -0.39133
    0.480       1.64078      0.193      -0.12084      -0.98547      0.170      8.0      -0.354      -0.08172      -0.03289      -0.00133      0.679      0.550      0.9441      0.6528      -0.94384      -0.38532
    0.500       1.56410      0.193      -0.12342      -0.97014      0.170      8.0      -0.354      -0.08511      -0.01297      -0.00127      0.673      0.550      0.9519      0.6496      -0.95097      -0.37956
    0.550       1.38635      0.193      -0.12955      -0.93538      0.170      8.0      -0.354      -0.09286       0.00000      -0.00113      0.660      0.550      0.9950      0.6487      -0.96584      -0.36610
    0.600       1.22784      0.193      -0.13530      -0.90533      0.170      8.0      -0.354      -0.09980       0.00000      -0.00099      0.647      0.550      1.0137      0.6535      -0.97746      -0.35382
    0.650       1.08684      0.193      -0.14070      -0.87944      0.170      8.0      -0.354      -0.10613       0.00000      -0.00087      0.633      0.550      1.0208      0.6655      -0.98670      -0.34252
    0.700       0.96118      0.193      -0.14577      -0.85717      0.170      8.0      -0.354      -0.11201       0.00000      -0.00076      0.620      0.550      1.0406      0.6683      -0.99416      -0.33206
    0.750       0.84856      0.193      -0.15056      -0.83799      0.170      8.0      -0.354      -0.11756       0.00000      -0.00066      0.620      0.550      1.0489      0.6582      -1.00027      -0.32233
    0.800       0.74687      0.193      -0.15509      -0.82143      0.170      8.0      -0.354      -0.12285       0.00000      -0.00056      0.620      0.550      1.0375      0.6562      -1.00532      -0.31322
    0.850       0.65430      0.193      -0.15938      -0.80711      0.170      8.0      -0.354      -0.12796       0.00000      -0.00047      0.620      0.550      1.0394      0.6470      -1.00956      -0.30466
    0.900       0.56939      0.193      -0.16345      -0.79468      0.170      8.0      -0.354      -0.13293       0.00000      -0.00038      0.620      0.550      1.0423      0.6488      -1.01314      -0.29659
    0.950       0.49101      0.193      -0.16731      -0.78385      0.170      8.0      -0.354      -0.13782       0.00000      -0.00030      0.620      0.550      1.0512      0.6383      -1.01619      -0.28896
    1.000       0.41833      0.193      -0.17099      -0.77438      0.170      8.0      -0.354      -0.14267       0.00000      -0.00022      0.620      0.550      1.0534      0.6342      -1.01881      -0.28172
    1.100       0.28765      0.193      -0.17784      -0.75874      0.170      8.0      -0.354      -0.14621       0.00000      -0.00008      0.620      0.550      1.0679      0.6204      -1.01720      -0.26827
    1.200       0.17365      0.193      -0.18409      -0.74652      0.170      8.0      -0.354      -0.14621       0.00000       0.00000      0.620      0.550      1.0859      0.6250      -1.00204      -0.25599
    1.300       0.07306      0.193      -0.18983      -0.73683      0.170      8.0      -0.354      -0.14621       0.00000       0.00000      0.620      0.550      1.0731      0.6291      -0.98810      -0.24469
    1.400      -0.01759      0.193      -0.19511      -0.72905      0.170      8.0      -0.354      -0.14621       0.00000       0.00000      0.620      0.550      1.0873      0.6199      -0.97519      -0.23423
    1.500      -0.10161      0.193      -0.19999      -0.72272      0.170      8.0      -0.354      -0.14621       0.00000       0.00000      0.620      0.550      1.0988      0.6173      -0.96317      -0.22449
    1.600      -0.18105      0.193      -0.20452      -0.71752      0.170      8.0      -0.354      -0.14621       0.00000       0.00000      0.620      0.550      1.1058      0.6120      -0.95193      -0.21538
    1.700      -0.25586      0.193      -0.20873      -0.71319      0.170      8.0      -0.354      -0.14621       0.00000       0.00000      0.620      0.550      1.1108      0.5923      -0.94136      -0.20682
    1.800      -0.32454      0.193      -0.21266      -0.70957      0.170      8.0      -0.354      -0.14621       0.00000       0.00000      0.620      0.550      1.1301      0.5859      -0.93141      -0.19876
    1.900      -0.38743      0.193      -0.21633      -0.70650      0.170      8.0      -0.354      -0.14621       0.00000       0.00000      0.620      0.550      1.1503      0.5787      -0.92199      -0.19112
    2.000      -0.45413      0.193      -0.21978      -0.70389      0.170      8.0      -0.354      -0.14621       0.00000       0.00000      0.620      0.550      1.1594      0.5724      -0.91305      -0.18388
    2.200      -0.58191      0.193      -0.22606      -0.69970      0.170      8.0      -0.354      -0.14621       0.00000       0.00000      0.620      0.550      1.1600      0.5943      -0.89645      -0.17043
    2.400      -0.68595      0.193      -0.23166      -0.69654      0.170      8.0      -0.354      -0.14621       0.00000       0.00000      0.620      0.550      1.1567      0.6100      -0.88129      -0.15815
    2.600      -0.78166      0.193      -0.23667      -0.69410      0.170      8.0      -0.354      -0.14621       0.00000       0.00000      0.620      0.550      1.1543      0.6053      -0.86735      -0.14685
    2.800      -0.87027      0.193      -0.24119      -0.69218      0.170      8.0      -0.354      -0.14621       0.00000       0.00000      0.620      0.550      1.1563      0.6098      -0.85444      -0.13639
    3.000      -0.95276      0.193      -0.24530      -0.69065      0.170      8.0      -0.354      -0.14621       0.00000       0.00000      0.620      0.550      1.1596      0.6251      -0.84242      -0.12665
    3.200      -1.02993      0.193      -0.24903      -0.68940      0.170      8.0      -0.354      -0.14621       0.00000       0.00000      0.620      0.550      1.1615      0.6362      -0.83118      -0.11754
    3.400      -1.10242      0.193      -0.25246      -0.68837      0.170      8.0      -0.354      -0.14621       0.00000       0.00000      0.620      0.550      1.1266      0.6360      -0.82062      -0.10899
    3.600      -1.17077      0.193      -0.25560      -0.68752      0.170      8.0      -0.354      -0.14621       0.00000       0.00000      0.620      0.550      1.0930      0.6231      -0.81066      -0.10092
    3.800      -1.23542      0.193      -0.25850      -0.68681      0.170      8.0      -0.354      -0.14621       0.00000       0.00000      0.620      0.550      1.0749      0.6244      -0.80124      -0.09329
    4.000      -1.29675      0.193      -0.26119      -0.68620      0.170      8.0      -0.354      -0.14621       0.00000       0.00000      0.620      0.550      1.0373      0.5409      -0.79231      -0.08605
    """)

    #: equation constants (that are IMT independent)
    CONSTS = {
        # coefficients in page 970 and table 4, page 973
        'c1': 6.75,
        'Vref': 750.0,
        'Vcon': 1000.0,
        'c': 2.5,
        'n': 3.2
    }


class KaleEtAl2015Iran(KaleEtAl2015Turkey):
    """
    Implements GMPE developed by O. Kale, S. Akkar, A. Ansari and H. Hamzehloo
    as published in "A ground-motion predictive model for Iran and Turkey for
    horizontal PGA, PGV and 5%-damped response spectrum: Investigation of
    possible regional effects", Bulletin of the Seismological Society of
    America (2015), 105(2A): 963 - 980. The class implements the equations for
    Joyner-Boore distance and based on manuscript provided by the original
    authors.

    Version calibrated for the Iran case
    """

    COEFFS = CoeffsTable(sa_damping=5, table="""\
      IMT             b1         b2            b3            b4         b5       b6         b7            b8             b9      b10         a1         a2         sd1         sd2           sb1           sb2
      pgv       5.791000      0.047      -0.19327      -0.89157      0.050      8.0      0.042       0.000000      -0.08609      0.0      0.700      0.440      0.9852      0.3439      -0.72057      -0.19688
      pga       1.529870      0.047      -0.10875      -1.00954      0.050      8.0      0.042      -0.130260      -0.09158      0.0      0.690      0.500      0.9713      0.3953      -0.41997      -0.28846
    0.010       1.530080      0.047      -0.10858      -1.00954      0.050      8.0      0.042      -0.130260      -0.09158      0.0      0.690      0.500      0.9721      0.3919      -0.41729      -0.28685
    0.020       1.547250      0.047      -0.10732      -1.01066      0.050      8.0      0.042      -0.130260      -0.09158      0.0      0.690      0.500      0.9723      0.3957      -0.39998      -0.28241
    0.030       1.622140      0.047      -0.10346      -1.02788      0.050      8.0      0.042      -0.130260      -0.09158      0.0      0.690      0.500      0.9754      0.3970      -0.34799      -0.26842
    0.040       1.751330      0.047      -0.09582      -1.05283      0.050      8.0      0.042      -0.130260      -0.09158      0.0      0.690      0.500      0.9960      0.4091      -0.27572      -0.24759
    0.050       1.920470      0.047      -0.09060      -1.07963      0.050      8.0      0.042      -0.130260      -0.09158      0.0      0.710      0.500      0.9909      0.4396      -0.21231      -0.22385
    0.075       2.395390      0.047      -0.09060      -1.13842      0.050      8.0      0.042      -0.130260      -0.09158      0.0      0.740      0.500      0.9698      0.4632      -0.13909      -0.17798
    0.100       2.700430      0.047      -0.09060      -1.17035      0.050      8.0      0.042      -0.130260      -0.09158      0.0      0.760      0.500      0.9943      0.4377      -0.26492      -0.28832
    0.110       2.740200      0.047      -0.09076      -1.16529      0.050      8.0      0.042      -0.130260      -0.09158      0.0      0.760      0.500      1.0025      0.4518      -0.31346      -0.31798
    0.120       2.743950      0.047      -0.09127      -1.15646      0.050      8.0      0.042      -0.130260      -0.09158      0.0      0.760      0.500      1.0074      0.4644      -0.36002      -0.34246
    0.130       2.727860      0.047      -0.09378      -1.14151      0.050      8.0      0.042      -0.130260      -0.09158      0.0      0.760      0.490      1.0286      0.4636      -0.40424      -0.36297
    0.140       2.706020      0.047      -0.09640      -1.12693      0.050      8.0      0.042      -0.130260      -0.09158      0.0      0.760      0.480      1.0320      0.4757      -0.44592      -0.38036
    0.150       2.684530      0.047      -0.09872      -1.11281      0.050      8.0      0.042      -0.130260      -0.09158      0.0      0.760      0.470      1.0457      0.4603      -0.48496      -0.39525
    0.160       2.659010      0.047      -0.10150      -1.09920      0.050      8.0      0.042      -0.130260      -0.09158      0.0      0.760      0.460      1.0681      0.4508      -0.52137      -0.40811
    0.170       2.625670      0.047      -0.10401      -1.08611      0.050      8.0      0.042      -0.130260      -0.09158      0.0      0.760      0.450      1.0723      0.4486      -0.55520      -0.41930
    0.180       2.591290      0.047      -0.10647      -1.07358      0.050      8.0      0.042      -0.130260      -0.09158      0.0      0.760      0.450      1.0806      0.4398      -0.58656      -0.42911
    0.190       2.555960      0.047      -0.10889      -1.06160      0.050      8.0      0.042      -0.130260      -0.09158      0.0      0.760      0.450      1.0799      0.4353      -0.61558      -0.43774
    0.200       2.519780      0.047      -0.11128      -1.05018      0.050      8.0      0.042      -0.130260      -0.09158      0.0      0.760      0.450      1.0862      0.4163      -0.64239      -0.44574
    0.220       2.445350      0.047      -0.11594      -1.02896      0.050      8.0      0.042      -0.083930      -0.09158      0.0      0.760      0.450      1.0809      0.4186      -0.69002      -0.45499
    0.240       2.369090      0.047      -0.12046      -1.00982      0.050      8.0      0.042      -0.038850      -0.09158      0.0      0.760      0.450      1.0631      0.4074      -0.73062      -0.45939
    0.260       2.292110      0.047      -0.12485      -0.99260      0.050      8.0      0.042       0.000000      -0.09158      0.0      0.760      0.450      1.0491      0.4021      -0.76530      -0.45988
    0.280       2.215510      0.047      -0.12911      -0.97712      0.050      8.0      0.042       0.000000      -0.09158      0.0      0.760      0.450      1.0422      0.3908      -0.79499      -0.45739
    0.300       2.140300      0.047      -0.13326      -0.96321      0.050      8.0      0.042       0.000000      -0.08973      0.0      0.760      0.450      1.0166      0.3896      -0.82052      -0.45287
    0.320       2.067340      0.047      -0.13729      -0.95071      0.050      8.0      0.042       0.000000      -0.08183      0.0      0.760      0.450      1.0083      0.3781      -0.84256      -0.44255
    0.340       1.997350      0.047      -0.14122      -0.93945      0.050      8.0      0.042       0.000000      -0.07010      0.0      0.760      0.450      1.0026      0.3923      -0.86167      -0.43399
    0.360       1.930870      0.047      -0.14504      -0.92931      0.050      8.0      0.042       0.000000      -0.04750      0.0      0.760      0.450      0.9987      0.3908      -0.87832      -0.42592
    0.380       1.868300      0.047      -0.14877      -0.92014      0.050      8.0      0.042       0.000000      -0.02277      0.0      0.760      0.450      0.9966      0.4017      -0.89288      -0.41829
    0.400       1.809870      0.047      -0.15240      -0.91185      0.050      8.0      0.042       0.000000       0.00000      0.0      0.760      0.450      0.9993      0.4105      -0.90568      -0.41105
    0.420       1.755660      0.047      -0.15594      -0.90433      0.050      8.0      0.042       0.000000       0.00000      0.0      0.760      0.450      0.9990      0.4179      -0.91697      -0.40417
    0.440       1.705630      0.047      -0.15940      -0.89750      0.050      8.0      0.042       0.000000       0.00000      0.0      0.760      0.450      0.9950      0.4236      -0.92698      -0.39760
    0.460       1.659630      0.047      -0.16277      -0.89128      0.050      8.0      0.042       0.000000       0.00000      0.0      0.760      0.450      0.9873      0.4346      -0.93589      -0.39133
    0.480       1.617450      0.047      -0.16606      -0.88560      0.050      8.0      0.042       0.000000       0.00000      0.0      0.760      0.450      0.9757      0.4596      -0.94384      -0.38532
    0.500       1.578790      0.047      -0.16928      -0.88040      0.050      8.0      0.042       0.000000       0.00000      0.0      0.760      0.450      0.9728      0.4772      -0.95097      -0.37956
    0.550       1.495230      0.047      -0.17700      -0.86922      0.050      8.0      0.042       0.000000       0.00000      0.0      0.760      0.450      0.9936      0.4778      -0.96584      -0.36610
    0.600       1.425760      0.047      -0.18430      -0.86011      0.050      8.0      0.042       0.000000       0.00000      0.0      0.760      0.450      1.0137      0.4353      -0.97746      -0.35382
    0.650       1.365020      0.047      -0.19121      -0.85261      0.050      8.0      0.042       0.000000       0.00000      0.0      0.760      0.450      1.0170      0.4330      -0.98670      -0.34252
    0.700       1.308850      0.047      -0.19777      -0.84636      0.050      8.0      0.042       0.000000       0.00000      0.0      0.760      0.450      1.0321      0.4161      -0.99416      -0.33206
    0.750       1.254680      0.047      -0.20401      -0.84111      0.050      8.0      0.042       0.000000       0.00000      0.0      0.760      0.463      1.0328      0.4203      -1.00027      -0.32233
    0.800       1.201420      0.047      -0.20994      -0.83664      0.050      8.0      0.042       0.000000       0.00000      0.0      0.760      0.475      1.0256      0.4290      -1.00532      -0.31322
    0.850       1.149110      0.047      -0.21559      -0.83282      0.050      8.0      0.042       0.000000       0.00000      0.0      0.770      0.488      1.0124      0.4120      -1.00956      -0.30466
    0.900       1.098490      0.047      -0.22099      -0.82953      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.500      1.0020      0.3758      -1.01314      -0.29659
    0.950       1.050420      0.047      -0.22614      -0.82667      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.513      0.9917      0.3677      -1.01619      -0.28896
    1.000       1.005570      0.047      -0.23107      -0.82417      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.525      0.9741      0.3773      -1.01881      -0.28172
    1.100       0.925840      0.047      -0.24031      -0.82003      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.550      0.9656      0.3540      -1.01720      -0.26827
    1.200       0.855520      0.047      -0.24882      -0.81676      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.575      0.9671      0.3627      -1.00204      -0.25599
    1.300       0.787690      0.047      -0.25667      -0.81414      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.600      0.9561      0.3779      -0.98810      -0.24469
    1.400       0.718900      0.047      -0.26395      -0.81200      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.600      0.9560      0.3703      -0.97519      -0.23423
    1.500       0.651500      0.047      -0.27072      -0.81023      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.600      0.9651      0.3815      -0.96317      -0.22449
    1.600       0.589490      0.047      -0.27703      -0.80876      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.600      0.9741      0.3927      -0.95193      -0.21538
    1.700       0.532580      0.047      -0.28293      -0.80751      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.600      0.9700      0.3873      -0.94136      -0.20682
    1.800       0.477180      0.047      -0.28845      -0.80644      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.600      0.9537      0.4025      -0.93141      -0.19876
    1.900       0.426200      0.047      -0.29363      -0.80552      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.600      0.9452      0.4161      -0.92199      -0.19112
    2.000       0.379480      0.047      -0.29851      -0.80472      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.600      0.9411      0.4242      -0.91305      -0.18388
    2.200       0.294500      0.047      -0.30745      -0.80342      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.600      0.9419      0.4278      -0.89645      -0.17043
    2.400       0.209520      0.047      -0.31544      -0.80240      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.600      0.9381      0.4450      -0.88129      -0.15815
    2.600       0.124530      0.047      -0.32264      -0.80159      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.600      0.9270      0.4518      -0.86735      -0.14685
    2.800       0.039550      0.047      -0.32915      -0.80093      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.600      0.9335      0.4726      -0.85444      -0.13639
    3.000      -0.045430      0.047      -0.33507      -0.80039      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.600      0.9334      0.4895      -0.84242      -0.12665
    3.200      -0.130410      0.047      -0.34048      -0.79994      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.600      0.9354      0.5096      -0.83118      -0.11754
    3.400      -0.215390      0.047      -0.34545      -0.79956      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.600      0.8628      0.4473      -0.82062      -0.10899
    3.600      -0.300380      0.047      -0.35002      -0.79924      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.600      0.8392      0.4401      -0.81066      -0.10092
    3.800      -0.385360      0.047      -0.35424      -0.79896      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.600      0.8146      0.4577      -0.80124      -0.09329
    4.000      -0.470340      0.047      -0.35815      -0.79872      0.050      8.0      0.042       0.000000       0.00000      0.0      0.780      0.600      0.8094      0.4547      -0.79231      -0.08605
    """)

    #: equation constants (that are IMT independent)
    CONSTS = {
        # coefficients in page 970 and table 4, page 973
        'c1': 7.0,
        'Vref': 750.0,
        'Vcon': 1000.0,
        'c': 2.5,
        'n': 3.2
    }
