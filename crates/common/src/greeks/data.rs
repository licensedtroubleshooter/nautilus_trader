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

//! Option Greeks data structures (delta, gamma, theta, vega, rho) used throughout the platform.

use std::{
    fmt::Display,
    ops::{Add, Mul},
};

use implied_vol::{DefaultSpecialFn, ImpliedBlackVolatility, SpecialFn};
use nautilus_core::{UnixNanos, math::quadratic_interpolation};
use nautilus_macros::custom_data;
use nautilus_model::identifiers::InstrumentId;

use crate::greeks::black_scholes::{compute_greeks, compute_iv_and_greeks};

const FRAC_SQRT_2_PI: f64 = f64::from_bits(0x3fd9884533d43651);
/// Used to convert theta to per-calendar-day change when building BlackScholesGreeksResult.
const THETA_DAILY_FACTOR: f64 = 1.0 / 365.25;
/// Scale for vega to express as absolute percent change when building BlackScholesGreeksResult.
const VEGA_PERCENT_FACTOR: f64 = 0.01;

#[inline(always)]
fn norm_pdf(x: f64) -> f64 {
    FRAC_SQRT_2_PI * (-0.5 * x * x).exp()
}

/// Result structure for Black-Scholes greeks calculations.
/// This is a separate f64 struct (not a type alias) for Python compatibility.
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, PartialOrd)]
#[cfg_attr(
    all(feature = "greeks", feature = "python"),
    pyo3::pyclass(module = "nautilus_trader.core.nautilus_pyo3.common", from_py_object)
)]
pub struct BlackScholesGreeksResult {
    pub price: f64,
    pub vol: f64,
    pub delta: f64,
    pub gamma: f64,
    pub vega: f64,
    pub theta: f64,
    pub itm_prob: f64,
}

// dS_t = S_t * (b * dt + vol * dW_t) (stock)
// dC_t = r * C_t * dt (cash numeraire)
#[allow(clippy::too_many_arguments)]
pub fn black_scholes_greeks_exact(
    s: f64,
    r: f64,
    b: f64,
    vol: f64,
    is_call: bool,
    k: f64,
    t: f64,
) -> BlackScholesGreeksResult {
    let phi = if is_call { 1.0 } else { -1.0 };
    let scaled_vol = vol * t.sqrt();
    let d1 = ((s / k).ln() + (b + 0.5 * vol.powi(2)) * t) / scaled_vol;
    let d2 = d1 - scaled_vol;
    let cdf_phi_d1 = DefaultSpecialFn::norm_cdf(phi * d1);
    let cdf_phi_d2 = DefaultSpecialFn::norm_cdf(phi * d2);
    let dist_d1 = norm_pdf(d1);
    let df = ((b - r) * t).exp();
    let s_t = s * df;
    let k_t = k * (-r * t).exp();

    let price = phi * (s_t * cdf_phi_d1 - k_t * cdf_phi_d2);
    let delta = phi * df * cdf_phi_d1;
    let gamma = df * dist_d1 / (s * scaled_vol);
    let vega = s_t * t.sqrt() * dist_d1 * VEGA_PERCENT_FACTOR;
    let theta = (s_t * (-dist_d1 * vol / (2.0 * t.sqrt()) - phi * (b - r) * cdf_phi_d1)
        - phi * r * k_t * cdf_phi_d2)
        * THETA_DAILY_FACTOR;
    let itm_prob = cdf_phi_d2;

    BlackScholesGreeksResult {
        price,
        vol,
        delta,
        gamma,
        vega,
        theta,
        itm_prob,
    }
}

pub fn imply_vol(s: f64, r: f64, b: f64, is_call: bool, k: f64, t: f64, price: f64) -> f64 {
    let forward = s * (b * t).exp();
    let forward_price = price * (r * t).exp();

    ImpliedBlackVolatility::builder()
        .option_price(forward_price)
        .forward(forward)
        .strike(k)
        .expiry(t)
        .is_call(is_call)
        .build_unchecked()
        .calculate::<DefaultSpecialFn>()
        .unwrap_or(0.0)
}

/// Computes Black-Scholes greeks using the fast compute_greeks implementation.
#[allow(clippy::too_many_arguments)]
pub fn black_scholes_greeks(
    s: f64,
    r: f64,
    b: f64,
    vol: f64,
    is_call: bool,
    k: f64,
    t: f64,
) -> BlackScholesGreeksResult {
    let greeks = compute_greeks::<f32>(
        s as f32, k as f32, t as f32, r as f32, b as f32, vol as f32, is_call,
    );

    BlackScholesGreeksResult {
        price: greeks.price as f64,
        vol,
        delta: greeks.delta as f64,
        gamma: greeks.gamma as f64,
        vega: (greeks.vega as f64) * VEGA_PERCENT_FACTOR,
        theta: (greeks.theta as f64) * THETA_DAILY_FACTOR,
        itm_prob: greeks.itm_prob as f64,
    }
}

/// Computes implied volatility and greeks using the fast implementations.
/// This function uses compute_greeks after implying volatility.
#[allow(clippy::too_many_arguments)]
pub fn imply_vol_and_greeks(
    s: f64,
    r: f64,
    b: f64,
    is_call: bool,
    k: f64,
    t: f64,
    price: f64,
) -> BlackScholesGreeksResult {
    let vol = imply_vol(s, r, b, is_call, k, t, price);
    // Handle case when imply_vol fails and returns 0.0 or very small value.
    // Using a very small vol (1e-8) instead of 0.0 prevents division by zero in greeks calculations.
    let safe_vol = if vol < 1e-8 { 1e-8 } else { vol };
    black_scholes_greeks(s, r, b, safe_vol, is_call, k, t)
}

/// Refines implied volatility using an initial guess and computes greeks.
/// This function uses compute_iv_and_greeks which performs a Halley iteration
/// to refine the volatility estimate from an initial guess.
#[allow(clippy::too_many_arguments)]
pub fn refine_vol_and_greeks(
    s: f64,
    r: f64,
    b: f64,
    is_call: bool,
    k: f64,
    t: f64,
    target_price: f64,
    initial_vol: f64,
) -> BlackScholesGreeksResult {
    let greeks = compute_iv_and_greeks::<f32>(
        target_price as f32,
        s as f32,
        k as f32,
        t as f32,
        r as f32,
        b as f32,
        is_call,
        initial_vol as f32,
    );

    BlackScholesGreeksResult {
        price: greeks.price as f64,
        vol: greeks.vol as f64,
        delta: greeks.delta as f64,
        gamma: greeks.gamma as f64,
        vega: (greeks.vega as f64) * VEGA_PERCENT_FACTOR,
        theta: (greeks.theta as f64) * THETA_DAILY_FACTOR,
        itm_prob: greeks.itm_prob as f64,
    }
}

#[custom_data(pyo3, no_display)]
pub struct GreeksData {
    pub ts_init: UnixNanos,
    pub ts_event: UnixNanos,
    pub instrument_id: InstrumentId,
    pub is_call: bool,
    pub strike: f64,
    pub expiry: i32,
    pub expiry_in_days: i32,
    pub expiry_in_years: f64,
    pub multiplier: f64,
    pub quantity: f64,
    pub underlying_price: f64,
    pub interest_rate: f64,
    pub cost_of_carry: f64,
    pub vol: f64,
    pub pnl: f64,
    pub price: f64,
    pub delta: f64,
    pub gamma: f64,
    pub vega: f64,
    pub theta: f64,
    pub itm_prob: f64,
}

impl GreeksData {
    /// Construct from delta (and optional multiplier). Used by Python `from_delta` and Rust callers.
    pub fn from_delta_rust(
        instrument_id: InstrumentId,
        delta: f64,
        multiplier: f64,
        ts_event: UnixNanos,
    ) -> Self {
        Self::new(
            ts_event,
            ts_event,
            instrument_id,
            true,
            0.0,
            0,
            0,
            0.0,
            multiplier,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            delta,
            0.0,
            0.0,
            0.0,
            0.0,
        )
    }
}

impl Default for GreeksData {
    fn default() -> Self {
        Self::new(
            UnixNanos::default(),
            UnixNanos::default(),
            InstrumentId::from("ES.GLBX"),
            true,
            0.0,
            0,
            0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        )
    }
}

impl Mul<&GreeksData> for f64 {
    type Output = GreeksData;

    fn mul(self, greeks: &GreeksData) -> GreeksData {
        GreeksData::new(
            greeks.ts_init,
            greeks.ts_event,
            greeks.instrument_id,
            greeks.is_call,
            greeks.strike,
            greeks.expiry,
            greeks.expiry_in_days,
            greeks.expiry_in_years,
            greeks.multiplier,
            greeks.quantity,
            greeks.underlying_price,
            greeks.interest_rate,
            greeks.cost_of_carry,
            greeks.vol,
            self * greeks.pnl,
            self * greeks.price,
            self * greeks.delta,
            self * greeks.gamma,
            self * greeks.vega,
            self * greeks.theta,
            greeks.itm_prob,
        )
    }
}

impl Display for GreeksData {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "GreeksData(instrument_id={}, expiry={}, itm_prob={:.2}%, vol={:.2}%, pnl={:.2}, price={:.2}, delta={:.2}, gamma={:.2}, vega={:.2}, theta={:.2}, quantity={}, ts_init={})",
            self.instrument_id,
            self.expiry,
            self.itm_prob * 100.0,
            self.vol * 100.0,
            self.pnl,
            self.price,
            self.delta,
            self.gamma,
            self.vega,
            self.theta,
            self.quantity,
            nautilus_core::datetime::unix_nanos_to_iso8601(self.ts_init)
        )
    }
}

#[custom_data(pyo3, no_display)]
pub struct PortfolioGreeks {
    pub ts_init: UnixNanos,
    pub ts_event: UnixNanos,
    pub pnl: f64,
    pub price: f64,
    pub delta: f64,
    pub gamma: f64,
    pub vega: f64,
    pub theta: f64,
}

impl Default for PortfolioGreeks {
    fn default() -> Self {
        Self::new(
            UnixNanos::default(),
            UnixNanos::default(),
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        )
    }
}

impl Add for PortfolioGreeks {
    type Output = Self;

    fn add(self, other: Self) -> Self {
        Self::new(
            self.ts_init,
            self.ts_event,
            self.pnl + other.pnl,
            self.price + other.price,
            self.delta + other.delta,
            self.gamma + other.gamma,
            self.vega + other.vega,
            self.theta + other.theta,
        )
    }
}

impl From<GreeksData> for PortfolioGreeks {
    fn from(greeks: GreeksData) -> Self {
        Self::new(
            greeks.ts_init,
            greeks.ts_event,
            greeks.pnl,
            greeks.price,
            greeks.delta,
            greeks.gamma,
            greeks.vega,
            greeks.theta,
        )
    }
}

impl Display for PortfolioGreeks {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "PortfolioGreeks(pnl={:.2}, price={:.2}, delta={:.2}, gamma={:.2}, vega={:.2}, theta={:.2}, ts_event={}, ts_init={})",
            self.pnl,
            self.price,
            self.delta,
            self.gamma,
            self.vega,
            self.theta,
            nautilus_core::datetime::unix_nanos_to_iso8601(self.ts_event),
            nautilus_core::datetime::unix_nanos_to_iso8601(self.ts_init)
        )
    }
}

#[custom_data(pyo3, no_display)]
pub struct YieldCurveData {
    pub ts_init: UnixNanos,
    pub ts_event: UnixNanos,
    pub curve_name: String,
    pub tenors: Vec<f64>,
    pub interest_rates: Vec<f64>,
}

impl YieldCurveData {
    pub fn get_rate(&self, expiry_in_years: f64) -> f64 {
        if self.interest_rates.len() == 1 {
            return self.interest_rates[0];
        }

        quadratic_interpolation(expiry_in_years, &self.tenors, &self.interest_rates)
    }
}

impl Default for YieldCurveData {
    fn default() -> Self {
        Self::new(
            UnixNanos::default(),
            UnixNanos::default(),
            "USD".to_string(),
            vec![0.5, 1.0, 1.5, 2.0, 2.5],
            vec![0.04, 0.04, 0.04, 0.04, 0.04],
        )
    }
}

impl Display for YieldCurveData {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "InterestRateCurve(curve_name={}, ts_event={}, ts_init={})",
            self.curve_name,
            nautilus_core::datetime::unix_nanos_to_iso8601(self.ts_event),
            nautilus_core::datetime::unix_nanos_to_iso8601(self.ts_init)
        )
    }
}
