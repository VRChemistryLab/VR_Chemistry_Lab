clear;
close all;

import cantera.*

gas  = Solution('na_br.yaml','gas');
surf = Interface('na_br.yaml','surface', gas);

p_atm = 1.01325e5; % Pa

% Initialize gas mixture (with inert gas as reference for mole fraction)
set(gas,'T', 350,'P',p_atm,'X','Br2:0.9, Ar:0.1');

% Initialize surface (room temperature)
set(surf,'T', 298.15,'P',p_atm);

% Initial surface coverages (PT = active surface site)
setCoverages(surf,'PT:0.05, Na_s:0.95');

r  = IdealGasReactor(gas);
rs = ReactorSurface(surf, r);

setArea(rs, 1e5); % m^2, Large surface to model strong coupling. Consider as effective number of reactive sites?

net = ReactorNet({r});

t_end = 1; % seconds
dt = 1e-5;
n = floor(t_end/dt);

time = zeros(n,1);
Br2  = zeros(n,1);
Na   = zeros(n,1);
NaBr = zeros(n,1);
T    = zeros(n,1);
p    = zeros(n,1);

names_surf = speciesNames(surf);

index_Na   = find(strcmp(names_surf,'Na_s'));
index_NaBr = find(strcmp(names_surf,'NaBr_s'));

t = 0;
for i = 1:n
    t = t + dt;
    advance(net, t);

    set(gas, 'T', temperature(r), 'P', pressure(r));
    Br2(i) = moleFraction(gas,'Br2');
    T(i)   = temperature(r);
    p(i)   = pressure(r);

    theta   = coverages(surf);
    Na(i)   = theta(index_Na);
    NaBr(i) = theta(index_NaBr);

    time(i) = t;
end

figure('Position',[100 200 500 300]);
plot(time, Br2,'LineWidth',2);
xlabel('Time [s]');
ylabel('Br_2 mole fraction');
title('Br_2 consumption');

figure('Position',[100 200 500 300]);
plot(time, Na,'LineWidth',2);
xlabel('Time [s]');
ylabel('Na surface coverage');
title('Na consumption');

figure('Position',[100 200 500 300]);
plot(time, NaBr,'LineWidth',2)
xlabel('Time [s]')
ylabel('NaBr surface coverage')
title('NaBr formation')

figure('Position',[100 200 500 300]);
plot(time, T,'LineWidth',2);
xlabel('Time [s]');
ylabel('Temperature [K]');
title('Reactor temperature');

figure('Position',[100 200 500 300]);
plot(time, p,'LineWidth',2);
xlabel('Time [s]');
ylabel('Pressure [Pa]');
title('Reactor pressure');