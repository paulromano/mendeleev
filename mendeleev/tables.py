# -*- coding: utf-8 -*-

#The MIT License (MIT)
#
#Copyright (c) 2015 Lukasz Mentel
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in all
#copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#SOFTWARE.

'''mendeleev module'''

import re
from collections import OrderedDict
from operator import attrgetter

from sqlalchemy import Column, Boolean, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship, reconstructor
#from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method

__all__ = ['Element', 'IonizationEnergy', 'IonicRadius', 'OxidationState',
           'Isotope', 'Series', 'ScreeningConstant']

subshells = ['s', 'p', 'd', 'f', 'g', 'h', 'i', 'j', 'k']
Base = declarative_base()

class Element(Base):
    '''
    Chemical element.

    Attributes:
      annotation : str
        Annotations regarding the data
      atomic_number : int
        Atomic number
      atomic_radius : float
        Atomic radius in pm
      atomic_volume : float
        Atomic volume in cm3/mol
      block : int
        Block in periodic table
      boiling_point : float
        Boiling temperature in K
      covalent_radius : float
        Covalent radius in pm
      density : float
        Density at 295K in g/cm3
      description : str
        Short description of the element
      dipole_polarizability : float
        Dipole polarizability in atomic units from P. Schwerdtfeger "Table of
        experimental and calculated static dipole polarizabilities for the
        electronic ground states of the neutral elements (in atomic units)",
        February 11, 2014
      electron_affinity : float
        Electron affinity in eV
      electronegativity : float
        Electronegativity (Pauling scale)
      econf : str
        Ground state electron configuration
      evaporation_heat : float
        Evaporation heat in kJ/mol
      fusion_heat : float
        Fusion heat in kJ/mol
      group : int
        Group in periodic table
      lattice_constant : float
        Lattice constant in ang
      lattice_structure : str
        Lattice structure code
      mass : float
        Relative atomic mass. Ratio of the average mass of atoms
        of the element to 1/12 of the mass of an atom of 12C
      melting_point : float
        Melting temperature in K
      name : str
        Name in english
      period : int
        Period in periodic table
      series : int
        Index to chemical series
      specific_heat : float
        Specific heat in J/g mol @ 20 C
      symbol : str of length 1 or 2
        Chemical symbol
      thermal_conductivity : float
        Thermal conductivity in @/m K @25 C
      vdw_radius : float
        Van der Waals radius in pm
      oxistates : str
        Oxidation states
      ionenergy : tuple
        Ionization energies in eV parsed from
        http://physics.nist.gov/cgi-bin/ASD/ie.pl on April 13, 2015
    '''

    __tablename__ = 'elements'

    annotation = Column(String)
    atomic_number = Column(Integer, primary_key=True)
    atomic_radius = Column(Float)
    atomic_volume = Column(Float)
    block = Column(String)
    boiling_point = Column(Float)
    covalent_radius = Column(Float)
    density = Column(Float)
    description = Column(String)
    dipole_polarizability = Column(Float)
    electron_affinity = Column(Float)
    electronegativity = Column(Float)
    econf = Column('electronic_configuration', String)
    evaporation_heat = Column(Float)
    fusion_heat = Column(Float)
    group = relationship("Group", uselist=False)
    group_id = Column(Integer, ForeignKey("groups.group_id"))
    lattice_constant = Column(Float)
    lattice_structure = Column(String)
    mass = Column(Float)
    melting_point = Column(String)
    name = Column(String)
    period = Column(Integer)
    _series_id = Column("series_id", Integer, ForeignKey("series.id"))
    _series = relationship("Series", uselist=False)
    series = association_proxy("_series", "name")
    specific_heat = Column(Float)
    symbol = Column(String)
    thermal_conductivity = Column(Float)
    vdw_radius = Column(Float)

    ionic_radii = relationship("IonicRadius")
    _ionization_energies = relationship("IonizationEnergy")
    _oxidation_states = relationship("OxidationState")
    isotopes = relationship("Isotope")
    screening_constants = relationship('ScreeningConstant')

    @reconstructor
    def init_on_load(self):

        self.ec = ElectronicConfiguration(self.econf)

    @hybrid_property
    def ionenergies(self):
        '''
        Return a dict with ionization degree as keys and ionization energies
        in eV as values.
        '''

        return {ie.degree:ie.energy for ie in self._ionization_energies}

    @hybrid_property
    def oxistates(self):
        '''Return the oxidation states as a list of ints'''

        return [os.oxidation_state for os in self._oxidation_states]

    @hybrid_property
    def sconst(self):
        '''
        Return a dict with screening constants with tuples (n, s) as keys and
        screening constants as values'''

        return {(x.n, x.s) : x.screening for x in self.screening_constants}

    @hybrid_property
    def electrons(self):
        '''Return the number of electrons.'''

        return self.atomic_number

    @hybrid_property
    def protons(self):
        '''Return the number of protons.'''

        return self.atomic_number

    @hybrid_property
    def neutrons(self):
        '''Return the number of neutrons of the most abundant natural stable isotope.'''

        return self.mass_number - self.protons

    @hybrid_property
    def mass_number(self):
        '''Return the mass number of the most abundant natural stable isotope.'''

        return max(self.isotopes, key=attrgetter("abundance")).mass_number

    @hybrid_method
    def abselen(self, charge=0):
        '''
        Return the absolute electronegativity, calculated as

        .. math::

           \chi = \frac{I + A}{2}

        where I is the ionization energy and A is the electron affinity
        '''

        if charge == 0:
            if self.ionenergies.get(1, None) is not None and\
                    self.electron_affinity is not None:
                return (self.ionenergies[1] + self.electron_affinity)*0.5
            else:
                return None
        elif charge > 0:
            if self.ionenergies.get(charge + 1, None) is not None and\
               self.ionenergies.get(charge, None) is not None:
                return (self.ionenergies[charge + 1] + self.ionenergies[charge])*0.5
            else:
                return None
        elif charge < 0:
            raise ValueError('Charge has to be a non-negative integer, got: {}'.format(charge))

    @hybrid_method
    def hardness(self, charge=0):
        '''
        Return the absolute hardness, calculated as

        .. math::

           \eta = \frac{I - A}{2}

        where I is the ionization energy and A is the electron affinity

        Args:
          charge: int
            Charge of the cation for which the hardness will be calculated
        '''

        if charge == 0:
            if self.ionenergies.get(1, None) is not None and self.electron_affinity is not None:
                return (self.ionenergies[1] - self.electron_affinity)*0.5
            else:
                return None
        elif charge > 0:
            if self.ionenergies.get(charge + 1, None) is not None and\
               self.ionenergies.get(charge, None) is not None:
                return (self.ionenergies[charge + 1] - self.ionenergies[charge])*0.5
            else:
                return None
        elif charge < 0:
            raise ValueError('Charge has to be a non-negative integer, got: {}'.format(charge))

    @hybrid_method
    def softness(self, charge=0):
        '''
        Return the absolute softness, calculated as

        .. math::

           S = \frac{1}{2\eta}

        where $\eta$ is the absolute hardness

        Args:
          charge: int
            Charge of the cation for which the hardness will be calculated
        '''

        eta = self.hardness(charge=charge)

        if eta is None:
            return None
        else:
            return 1.0/(2.0*eta)

    @hybrid_property
    def exact_mass(self):
        '''Return the mass calculated from isotopic composition.'''

        return sum(iso.mass * iso.abundance for iso in self.isotopes)

    def zeff(self, n=None, s=None, method='slater'):
        '''
        Return the effective nuclear charge for (n, s)

        Args:
          method : str
            Method to calculate the screening constant, the choices are
              - `slater`, for Slater's method as in Slater, J. C. (1930).
                Atomic Shielding Constants. Physical Review, 36(1), 57–64.
                `doi:10.1103/PhysRev.36.57 <http://www.dx.doi.org/10.1103/PhysRev.36.57>`_
              - `clementi` for values of screening constants from Clementi, E.,
                & Raimondi, D. L. (1963). Atomic Screening Constants from SCF
                Functions. The Journal of Chemical Physics, 38(11), 2686.
                `doi:10.1063/1.1733573 <http://www.dx.doi.org/10.1063/1.1733573`_
                and Clementi, E. (1967). Atomic Screening Constants from SCF
                Functions. II. Atoms with 37 to 86 Electrons. The Journal of
                Chemical Physics, 47(4), 1300.
                `doi:10.1063/1.1712084 <http://www.dx.doi.org/10.1063/1.1712084>`_
          n : int
            Principal quantum number
          s : str
            Subshell label, (s, p, d, ...)
        '''

        # identify th valence s,p vs d,f
        if n is None:
            n = self.ec.maxn()
        else:
            if not isinstance(n, int):
                raise ValueError('<n> should be an integer, got'.format(typ(n)))

        if s is None:
            s = subshells[max([subshells.index(x[1]) for x in self.ec.conf.keys() if x[0] == n])]
        else:
            if s not in subshells:
                raise ValueError('<s> should be one of {}'.format(", ".join(subshells)))

        if method.lower() == 'slater':
            return self.atomic_number - self.ec.slater_screening(n=n, s=s)
        elif method.lower() == 'clementi':
            return self.atomic_number - self.sconst[n,s]
        else:
            raise ValueError('<method> should be one of {}'.format("slater, clementi"))

    def __str__(self):
        return "{0} {1} {2}".format(self.atomic_number, self.symbol, self.name)

    def __repr__(self):
        return "%s(\n%s)" % (
                 (self.__class__.__name__),
                 ' '.join(["\t%s=%r,\n" % (key, getattr(self, key))
                            for key in sorted(self.__dict__.keys())
                            if not key.startswith('_')]))

class IonicRadius(Base):
    '''
    Effective ionic radii and crystal radii in pm retrieved from [1].

    .. [1] Shannon, R. D. (1976). Revised effective ionic radii and systematic
       studies of interatomic distances in halides and chalcogenides. Acta
       Crystallographica Section A. `doi:10.1107/S0567739476001551 <http://www.dx.doi.org/10.1107/S0567739476001551>`_

    Attributes:
      atomic_number : int
        Atomic number
      charge : int
        Charge of the ion
      econf : str
        Electronic configuration of the ion
      coordination : str
        Type of coordination
      spin : str
        Spin state: HS - high spin, LS - low spin
      crystal_radius : float
        Crystal radius in pm
      ionic_radius : float
        Ionic radius in pm
      origin : str
        Source of the data
      most_reliable : bool
    '''

    __tablename__ = 'ionicradii'

    id = Column(Integer, primary_key=True)
    atomic_number = Column(Integer, ForeignKey('elements.atomic_number'))
    charge = Column(Integer)
    econf = Column(String)
    coordination = Column(String)
    spin = Column(String)
    crystal_radius = Column(Float)
    ionic_radius = Column(Float)
    origin = Column(String)
    most_reliable = Column(Boolean)

    def __str__(self):
        out = ["{0}={1:>4d}", "{0}={1:5s}", "{0}={1:>6.3f}", "{0}={1:>6.3f}"]
        keys = ['charge', 'coordination', 'crystal_radius', 'ionic_radius']
        return ", ".join([o.format(k, getattr(self, k)) for o, k in zip(out, keys)])

    def __repr__(self):
        return "%s(\n%s)" % (
                 (self.__class__.__name__),
                 ' '.join(["\t%s=%r,\n" % (key, getattr(self, key))
                            for key in sorted(self.__dict__.keys())
                            if not key.startswith('_')]))

class IonizationEnergy(Base):
    '''
    Ionization energy of an element

    Attributes:
      atomic_number : int
        Atomic number
      degree : int
        Degree of ionization with respect to neutral atom
      energy : float
        Ionization energy in eV parsed from
        http://physics.nist.gov/cgi-bin/ASD/ie.pl on April 13, 2015
    '''

    __tablename__ = 'ionizationenergies'

    id = Column(Integer, primary_key=True)
    atomic_number = Column(Integer, ForeignKey('elements.atomic_number'))
    degree = Column(Integer)
    energy = Column(Float)

    def __str__(self):

        return "{1:5d} {2:10.5f}".format(self.degree, self.energy)

    def __repr__(self):

        return "<IonizationEnergy(atomic_number={a:5d}, degree={d:3d}, energy={e:10.5f})>".format(
               a=self.atomic_number, d=self.degree, e=self.energy)

class OxidationState(Base):
    '''
    Oxidation states of an element

    Attributes:
      atomic_number : int
        Atomic number
      oxidation_state : int
        Oxidation state
    '''

    __tablename__ = 'oxidationstates'

    id = Column(Integer, primary_key=True)
    atomic_number = Column(Integer, ForeignKey("elements.atomic_number"))
    oxidation_state = Column(Integer)

    def __repr__(self):

        return "<OxidationState(atomic_number={a:5d}, oxidation_state={o:5d})>".format(
               a=self.atomic_number, o=self.oxidation_state)

class Group(Base):
    '''Name of the group in the periodic table.'''

    __tablename__ = 'groups'

    group_id = Column(Integer, primary_key=True)
    symbol = Column(String)
    name = Column(String)

    def __repr__(self):

        return "<Group(symbol={s:s}, name={n:s})>".format(
               s=self.symbol, n=self.name)

class Series(Base):
    '''
    Name of the series in the periodic table.

    Attributes:
      name : str
        Name of the series
    '''

    __tablename__ = 'series'

    id = Column(Integer, primary_key=True)
    name = Column(String)

    def __repr__(self):

        return "<Series(name={n:s})>".format(n=self.name)

class Isotope(Base):
    '''
    Isotope

    Attributes:
      atomic_number : int
        Atomic number
      mass : float
        Mass of the isotope
      abundance : float
        Abundance of the isotope
      mass_number : int
        Mass number of the isotope
    '''

    __tablename__ = "isotopes"

    id = Column(Integer, primary_key=True)
    atomic_number = Column(Integer, ForeignKey("elements.atomic_number"))
    mass = Column(Float)
    abundance = Column(Float)
    mass_number = Column(Integer)

    def __str__(self):

        return "{0:5d} {1:10.5f} {2:6.2f}% {3:5d}".format(
                self.atomic_number, self.mass, self.abundance*100, self.mass_number)

    def __repr__(self):

        return "<Isotope(mass={}, abundance={}, mass_number={})>".format(
               self.mass, self.abundance, self.mass_number)

class ScreeningConstant(Base):
    '''
    Nuclear screening constants from Clementi, E., & Raimondi, D. L. (1963).
    Atomic Screening Constants from SCF Functions. The Journal of Chemical
    Physics, 38(11), 2686.  `doi:10.1063/1.1733573
    <http://www.dx.doi.org/10.1063/1.1733573`_ and Clementi, E. (1967). Atomic
    Screening Constants from SCF Functions. II. Atoms with 37 to 86 Electrons.
    The Journal of Chemical Physics, 47(4), 1300.  `doi:10.1063/1.1712084
    <http://www.dx.doi.org/10.1063/1.1712084>`_

    Attributes:
      atomic_number : int
        Atomic number
      n : int
        Principal quantum number
      s : str
        Subshell label, (s, p, d, ...)
      screening : float
        Screening constant
    '''

    __tablename__ = 'screeningconstants'

    id = Column(Integer, primary_key=True)
    atomic_number = Column(Integer, ForeignKey("elements.atomic_number"))
    n = Column(Integer)
    s = Column(String)
    screening = Column(Float)

    def __str__(self):

        return "{0:4d} {1:3d} {2:s} {3:10.4f}".format(self.atomic_number, self.n, self.s, self.screening)

    def __repr__(self):

        return "<ScreeningConstant(Z={0:4d}, n={1:3d}, s={2:s}, screening={3:10.4f})>".format(
                self.atomic_number, self.n, self.s, self.screening)

class ElectronicConfiguration(object):
    '''Electronic configuration handler'''

    def __init__(self, confstr, atomre=None, shellre=None):

        self.noble = {
            'He' : '1s2',
            'Ne' : '1s2 2s2 2p6',
            'Ar' : '1s2 2s2 2p6 3s2 3p6',
            'Kr' : '1s2 2s2 2p6 3s2 3p6 4s2 3d10 4p6',
            'Xe' : '1s2 2s2 2p6 3s2 3p6 4s2 3d10 4p6 5s2 4d10 5p6',
            'Rn' : '1s2 2s2 2p6 3s2 3p6 4s2 3d10 4p6 5s2 4d10 5p6 6s2 4f14 5d10 6p6'
        }

        self.confstr = confstr
        self.atomre = atomre
        self.shellre = shellre

        # parse the confstr and initialize core, valence and conf attributes
        self.parse()

    @property
    def atomre(self):
        return self._atomre

    @atomre.setter
    def atomre(self, value):

        if value is None:
            self._atomre = re.compile(r'\[([A-Z][a-z]*)\]')
        else:
            self._atomre = re.compile(value)

    @property
    def shellre(self):
        return self._shellre

    @shellre.setter
    def shellre(self, value):

        if value is None:
            self._shellre = re.compile(r'(?P<n>\d)(?P<s>[spdfghijk])(?P<e>\d+)?')
        else:
            self._shellre = re.compile(value)

    def parse(self):

        citems = self.confstr.split()

        core = {}
        calence = {}

        if self.atomre.match(citems[0]):
            symbol = str(self.atomre.match(citems[0]).group(1))
            citems = citems[1:]
            core = [self.shellre.match(s).group('n', 's', 'e')
                       for s in self.noble[symbol].split() if self.shellre.match(s)]
        valence = [self.shellre.match(s).group('n', 's', 'e')
                       for s in citems if self.shellre.match(s)]

        self.core = OrderedDict([((int(n), s) , (int(e) if e is not None else 1)) for (n, s, e) in core])
        self.valence = OrderedDict([((int(n), s), (int(e) if e is not None else 1)) for (n, s, e) in valence])
        self.conf = OrderedDict(self.core.items() + self.valence.items())

    def sort(self, inplace=True):

        if inplace:
            self.conf = OrderedDict(sorted(self.conf.items(), key=lambda x: (x[0][0]+subshells.index(x[0][1]), x[0][0])))
        else:
            OrderedDict(sorted(self.conf.items(), key=lambda x: (x[0][0]+subshells.index(x[0][1]), x[0][0])))

    def electrons_per_shell(self):

        pass

    def __repr__(self):

        return self.conf2str(self.conf)

    def __str__(self):

        return self.conf2str(self.conf)

    @staticmethod
    def conf2str(dictlike):

        return " ".join(["{n:d}{s:s}{e:d}".format(n=k[0], s=k[1], e=v) for k, v in dictlike.items()])

    def shell2int(self):

        return [(x[0], subshells.index(x[1]), x[2]) for x in self.conf]

    def maxn(self):

        return max([shell[0] for shell in self.conf.keys()])

    def slater_screening(self, n, s):
        '''
        Calculate the screening constant using the papproach introduced by
        Slater in Slater, J. C. (1930). Atomic Shielding Constants. Physical
        Review, 36(1), 57–64.
        `doi:10.1103/PhysRev.36.57 <http://www.dx.doi.org/10.1103/PhysRev.36.57>`_

        Args:
          n : int
            Principal quantum number
          s : str
            Subshell label, (s, p, d, ...)
        '''

        if n == 1:
            coeff = 0.3
        else:
            coeff = 0.35

        if s in ['s', 'p']:
            # get the number of valence electrons - 1
            vale = float(sum([v for k, v in self.conf.items() if k[0] == n and k[1] in ['s', 'p']]) - 1)
            n1 = sum([v*0.85 for k, v in self.conf.items() if k[0] == n-1])
            n2 = sum([float(v) for k, v in self.conf.items() if k[0] in range(1, n-1)])
            return n1 + n2 + vale*coeff
        elif s in ['d', 'f']:
            # get the number of valence electrons - 1
            vale = float(sum([v for k, v in self.conf.items() if k[0] == n and k[1] == s]) - 1)
            n1 = sum([float(v) for k, v in self.conf.items() if k[0] == n and k[1] != s])
            n2 = sum([float(v) for k, v in self.conf.items() if k[0] in range(1, n)])
            return n1 + n2 + vale*coeff
        else:
            raise ValueError('wrong valence subshell: ', s)