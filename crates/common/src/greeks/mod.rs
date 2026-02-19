// -------------------------------------------------------------------------------------------------
//  Copyright (C) 2015-2026 Nautech Systems Pty Ltd. All rights reserved.
//  https://nautechsystems.io
//
//  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
//  You may not use this file except in compliance with the License.
//  You may obtain a copy of the License at https://www.gnu.org/licenses/lgpl-3.0.en.html
//
//  Unless required by applicable law or agreed to in writing, software
//  distributed under the License is distributed on an "AS IS" BASIS,
//  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//  See the License for the specific language governing permissions and
//  limitations under the License.
// -------------------------------------------------------------------------------------------------

//! Option Greeks (delta, gamma, theta, vega) and Black-Scholes machinery.

pub mod black_scholes;
pub mod calculator;
pub mod data;

pub use black_scholes::{BlackScholesReal, Greeks, compute_greeks, compute_iv_and_greeks};
pub use calculator::{
    GreeksCalculator, GreeksFilter, GreeksFilterCallback, InstrumentGreeksParams,
    InstrumentGreeksParamsBuilder, PortfolioGreeksParams, PortfolioGreeksParamsBuilder,
};
pub use data::{
    BlackScholesGreeksResult, GreeksData, PortfolioGreeks, YieldCurveData, black_scholes_greeks,
    black_scholes_greeks_exact, imply_vol, imply_vol_and_greeks, refine_vol_and_greeks,
};
