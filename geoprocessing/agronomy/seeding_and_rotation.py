"""Herramientas 5 y 6: Calculadora de Siembra/Fertilización (Tablas INTA) y Comparador de Rotaciones Trienales."""

from __future__ import annotations

from geoprocessing.agronomy.erosion_usle import compute_usle_erosion_and_gullies
from geoprocessing.rainfall.nrcs_cn import CN_II_LOOKUP, SoilGroup, compute_nrcs_cn, lookup_cn_ii

# Parámetros agronómicos de referencia basados en guías técnicas de INTA / IPNI Cono Sur
INTA_CROP_SEEDING_TABLE: dict[str, dict] = {
    "maiz_temprano": {
        "label": "Maíz Temprano (grano)",
        "cover_code": "soja_maiz_sd_buena",
        "row_spacing_m": 0.52,
        "target_plants_ha_by_zone": {
            "loma": 68_000,
            "media_loma": 76_000,
            "bajo": 60_000,
        },
        "default_pms_g": 310.0,
        "default_pg_pct": 95.0,
        "default_purity_pct": 99.0,
        "implantation_efficiency_pct": 92.0,
        "bag_seeds_or_kg": "80.000 semillas/bolsa",
        "seeds_per_bag": 80_000,
        "default_target_yield_t_ha": 9.5,
        # Requerimiento de absorción por tonelada de grano (kg nutriente / t grano, IPNI/INTA)
        "nutrient_kg_per_t": {"N": 22.0, "P": 4.0, "S": 4.0},
        "sowing_window": "15 de septiembre al 20 de octubre (suelo > 12 °C)",
    },
    "maiz_tardio": {
        "label": "Maíz Tardío / de 2ª (estabilidad hídrica)",
        "cover_code": "soja_maiz_sd_buena",
        "row_spacing_m": 0.52,
        "target_plants_ha_by_zone": {
            "loma": 58_000,
            "media_loma": 65_000,
            "bajo": 54_000,
        },
        "default_pms_g": 300.0,
        "default_pg_pct": 95.0,
        "default_purity_pct": 99.0,
        "implantation_efficiency_pct": 92.0,
        "bag_seeds_or_kg": "80.000 semillas/bolsa",
        "seeds_per_bag": 80_000,
        "default_target_yield_t_ha": 8.0,
        "nutrient_kg_per_t": {"N": 22.0, "P": 4.0, "S": 4.0},
        "sowing_window": "25 de noviembre al 20 de diciembre",
    },
    "soja_primera": {
        "label": "Soja de 1ª (inoculada)",
        "cover_code": "soja_maiz_sd_buena",
        "row_spacing_m": 0.42,
        "target_plants_ha_by_zone": {
            "loma": 300_000,
            "media_loma": 280_000,
            "bajo": 320_000,
        },
        "default_pms_g": 165.0,
        "default_pg_pct": 90.0,
        "default_purity_pct": 98.0,
        "implantation_efficiency_pct": 88.0,
        "bag_seeds_or_kg": "Bolsa de 40 kg",
        "bag_weight_kg": 40.0,
        "default_target_yield_t_ha": 3.8,
        # En soja el N proviene ~60-70% de fijación biológica (FBN); se calcula P y S de reposición
        "nutrient_kg_per_t": {"N": 8.0, "P": 7.0, "S": 4.5},
        "sowing_window": "25 de octubre al 25 de noviembre (suelo > 15 °C)",
    },
    "trigo": {
        "label": "Trigo pan (ciclo intermedio/largo)",
        "cover_code": "trigo_cereal_invierno_sd",
        "row_spacing_m": 0.21,
        "target_plants_ha_by_zone": {
            "loma": 240_0000,
            "media_loma": 260_0000,
            "bajo": 220_0000,
        },
        "default_pms_g": 38.0,
        "default_pg_pct": 92.0,
        "default_purity_pct": 98.0,
        "implantation_efficiency_pct": 88.0,
        "bag_seeds_or_kg": "Bolsa de 40 kg",
        "bag_weight_kg": 40.0,
        "default_target_yield_t_ha": 4.2,
        "nutrient_kg_per_t": {"N": 30.0, "P": 5.0, "S": 4.5},
        "sowing_window": "20 de mayo al 10 de julio",
    },
    "girasol": {
        "label": "Girasol (alto oleico / convencional)",
        "cover_code": "soja_maiz_sd_buena",
        "row_spacing_m": 0.52,
        "target_plants_ha_by_zone": {
            "loma": 48_000,
            "media_loma": 52_000,
            "bajo": 42_000,
        },
        "default_pms_g": 65.0,
        "default_pg_pct": 92.0,
        "default_purity_pct": 99.0,
        "implantation_efficiency_pct": 90.0,
        "bag_seeds_or_kg": "150.000 semillas/bolsa",
        "seeds_per_bag": 150_000,
        "default_target_yield_t_ha": 2.8,
        "nutrient_kg_per_t": {"N": 40.0, "P": 7.0, "S": 5.0},
        "sowing_window": "1 de octubre al 10 de noviembre (suelo > 10 °C)",
    },
    "sorgo_granifero": {
        "label": "Sorgo Granífero (rastrojo abundante)",
        "cover_code": "soja_maiz_sd_buena",
        "row_spacing_m": 0.52,
        "target_plants_ha_by_zone": {
            "loma": 140_000,
            "media_loma": 160_000,
            "bajo": 150_000,
        },
        "default_pms_g": 28.0,
        "default_pg_pct": 88.0,
        "default_purity_pct": 98.0,
        "implantation_efficiency_pct": 85.0,
        "bag_seeds_or_kg": "Bolsa de 20 kg",
        "bag_weight_kg": 20.0,
        "default_target_yield_t_ha": 6.5,
        "nutrient_kg_per_t": {"N": 25.0, "P": 4.5, "S": 3.5},
        "sowing_window": "1 de noviembre al 15 de diciembre (suelo > 16 °C)",
    },
    "vicia_centeno_cobertura": {
        "label": "Cultivo de Servicio (Vicia villosa + Centeno)",
        "cover_code": "cultivo_cobertura_vicia_centeno",
        "row_spacing_m": 0.21,
        "target_plants_ha_by_zone": {
            "loma": 150_0000,
            "media_loma": 160_0000,
            "bajo": 170_0000,
        },
        "default_pms_g": 28.0,
        "default_pg_pct": 88.0,
        "default_purity_pct": 97.0,
        "implantation_efficiency_pct": 85.0,
        "bag_seeds_or_kg": "Bolsa de 25 kg",
        "bag_weight_kg": 25.0,
        "default_target_yield_t_ha": 5.5,  # t MS/ha de biomasa aérea
        "nutrient_kg_per_t": {"N": 3.0, "P": 3.0, "S": 2.0},
        "sowing_window": "15 de marzo al 15 de mayo",
    },
}


def calculate_seeding_and_fertilizer(
    crop_code: str,
    field_area_ha: float,
    soil_group: SoilGroup = "B",
    environment_zone: str = "media_loma",
    target_yield_t_ha: float | None = None,
    pms_g: float | None = None,
    pg_pct: float | None = None,
    purity_pct: float | None = None,
    row_spacing_m: float | None = None,
) -> dict:
    """Herramienta 5: Calcula densidad, semilla (kg/ha y total lote) y fertilizante (N-P-S) según INTA."""
    crop = INTA_CROP_SEEDING_TABLE.get(crop_code, INTA_CROP_SEEDING_TABLE["maiz_temprano"])
    target_plants = int(
        crop["target_plants_ha_by_zone"].get(
            environment_zone, crop["target_plants_ha_by_zone"]["media_loma"]
        )
    )
    pms = float(pms_g if pms_g is not None else crop["default_pms_g"])
    pg = float(pg_pct if pg_pct is not None else crop["default_pg_pct"])
    pur = float(purity_pct if purity_pct is not None else crop["default_purity_pct"])
    eff = float(crop["implantation_efficiency_pct"])
    row_m = float(row_spacing_m if row_spacing_m is not None else crop["row_spacing_m"])
    yield_t = float(target_yield_t_ha if target_yield_t_ha is not None else crop["default_target_yield_t_ha"])

    # Coeficiente de logro (0..1)
    achievement_ratio = max(0.25, (pg / 100.0) * (pur / 100.0) * (eff / 100.0))
    seeds_to_sow_ha = target_plants / achievement_ratio
    seeds_per_linear_m = (seeds_to_sow_ha * row_m) / 10_000.0
    seed_kg_ha = (seeds_to_sow_ha * pms) / 1_000_000.0
    total_seed_kg = seed_kg_ha * float(field_area_ha)

    if "seeds_per_bag" in crop:
        bags_needed = (seeds_to_sow_ha * float(field_area_ha)) / float(crop["seeds_per_bag"])
    else:
        bags_needed = total_seed_kg / float(crop.get("bag_weight_kg", 40.0))

    # Requerimiento nutricional N-P-S (kg/ha) y equivalentes comerciales orientativos
    # Aporte mineral estimado del suelo según grupo (A menor materia orgánica, B mayor mineralización)
    soil_n_credit = {"A": 35.0, "B": 65.0, "C": 50.0, "D": 30.0}.get(soil_group, 50.0)
    req_n = max(0.0, yield_t * crop["nutrient_kg_per_t"]["N"] - (soil_n_credit if "soja" not in crop_code else 0.0))
    req_p = yield_t * crop["nutrient_kg_per_t"]["P"]
    req_s = yield_t * crop["nutrient_kg_per_t"]["S"]

    # MAP (11-52-0): aporta 22.7 % P elemental (52 % P2O5) y 11 % N
    map_kg_ha = req_p / 0.227
    n_from_map = map_kg_ha * 0.11
    # Urea (46-0-0): aporta 46 % N
    urea_kg_ha = max(0.0, (req_n - n_from_map) / 0.46)
    # Yeso agrícola (Sulfato de calcio ~17 % S)
    gypsum_kg_ha = req_s / 0.17

    return {
        "crop_code": crop_code,
        "crop_label": crop["label"],
        "sowing_window_inta": crop["sowing_window"],
        "environment_zone": environment_zone,
        "soil_group": soil_group,
        "field_area_ha": round(float(field_area_ha), 2),
        "row_spacing_m": round(row_m, 2),
        "target_plants_ha": target_plants,
        "achievement_ratio_pct": round(achievement_ratio * 100.0, 1),
        "seeds_to_sow_ha": int(round(seeds_to_sow_ha)),
        "seeds_per_linear_m": round(seeds_per_linear_m, 2),
        "seed_density_kg_ha": round(seed_kg_ha, 1),
        "total_seed_kg_for_field": round(total_seed_kg, 1),
        "commercial_bags_needed": round(bags_needed, 1),
        "bag_unit": crop["bag_seeds_or_kg"],
        "target_yield_t_ha": round(yield_t, 2),
        "nutrients_required_kg_ha": {
            "N": round(req_n, 1),
            "P_elemental": round(req_p, 1),
            "P2O5_equiv": round(req_p * 2.29, 1),
            "S": round(req_s, 1),
        },
        "commercial_fertilizer_guide_kg_ha": {
            "MAP_11_52_0_kg_ha": round(map_kg_ha, 1),
            "Urea_46_0_0_kg_ha": round(urea_kg_ha, 1),
            "Yeso_agricola_17S_kg_ha": round(gypsum_kg_ha, 1),
        },
        "notes": [
            "Valores orientativos basados en tablas de extracción INTA / IPNI Cono Sur.",
            "Ajustar dosis de fertilización con análisis químico de suelo (P Bray, N-NO3 0-60 cm y S-SO4) previo a la siembra.",
        ],
    }


def compare_triennial_rotations(
    sequence_a_name: str,
    sequence_a_crops: list[str],
    sequence_b_name: str,
    sequence_b_crops: list[str],
    soil_group: SoilGroup,
    design_storm_mm: float,
    mfd_area_m2,
    slope_pct,
    spi,
    mascara_lote,
    pixel_size_m: float,
) -> dict:
    """Herramienta 6: Compara lado a lado escurrimiento, erosión y cobertura de 2 rotaciones trienales."""
    COVER_PCT_BY_CODE = {
        "soja_maiz_sd_buena": 65.0,
        "soja_maiz_convencional": 20.0,
        "trigo_cereal_invierno_sd": 80.0,
        "cultivo_cobertura_vicia_centeno": 90.0,
        "pastura_pradera_buena": 95.0,
        "pastura_sobrepastoreada": 40.0,
        "barbecho_con_rastrojo": 50.0,
        "barbecho_suelo_desnudo": 5.0,
    }

    def _eval_seq(seq_name: str, codes: list[str]) -> dict:
        years_out = []
        for yr_idx, code in enumerate(codes[:3], start=1):
            cov_pct = COVER_PCT_BY_CODE.get(code, 55.0)
            cn_ii, _ = lookup_cn_ii(code, soil_group, cover_percent=cov_pct)
            cn_res = compute_nrcs_cn(design_storm_mm, cn_ii, "medium", 0.2)
            _, ero_sum = compute_usle_erosion_and_gullies(
                mfd_area_m2=mfd_area_m2,
                slope_pct=slope_pct,
                spi=spi,
                mascara_lote=mascara_lote,
                pixel_size_m=pixel_size_m,
                precipitation_mm=design_storm_mm,
                runoff_q_mm=cn_res.runoff_q_mm,
                soil_group=soil_group,
                cover_code=code,
            )
            years_out.append({
                "year": yr_idx,
                "cover_code": code,
                "cover_label": CN_II_LOOKUP.get(code, {}).get("label", code),
                "cover_percent": cov_pct,
                "cn_effective": cn_res.cn_effective,
                "runoff_q_mm": cn_res.runoff_q_mm,
                "soil_loss_t_ha": ero_sum["mean_soil_loss_t_ha"],
                "total_field_soil_loss_tons": ero_sum["total_field_soil_loss_tons"],
            })

        mean_cn = sum(y["cn_effective"] for y in years_out) / max(1, len(years_out))
        mean_cover = sum(y["cover_percent"] for y in years_out) / max(1, len(years_out))
        total_q = sum(y["runoff_q_mm"] for y in years_out)
        total_loss_t_ha = sum(y["soil_loss_t_ha"] for y in years_out)
        total_loss_tons = sum(y["total_field_soil_loss_tons"] for y in years_out)
        return {
            "name": seq_name,
            "years": years_out,
            "mean_cn_3yr": round(mean_cn, 1),
            "mean_cover_pct_3yr": round(mean_cover, 1),
            "cumulative_runoff_3yr_mm": round(total_q, 2),
            "cumulative_soil_loss_3yr_t_ha": round(total_loss_t_ha, 3),
            "cumulative_field_soil_loss_3yr_tons": round(total_loss_tons, 2),
        }

    eval_a = _eval_seq(sequence_a_name, sequence_a_crops)
    eval_b = _eval_seq(sequence_b_name, sequence_b_crops)

    saved_runoff_mm = round(eval_a["cumulative_runoff_3yr_mm"] - eval_b["cumulative_runoff_3yr_mm"], 2)
    saved_soil_tons = round(
        eval_a["cumulative_field_soil_loss_3yr_tons"] - eval_b["cumulative_field_soil_loss_3yr_tons"],
        2,
    )

    return {
        "design_storm_mm": design_storm_mm,
        "soil_group": soil_group,
        "sequence_a": eval_a,
        "sequence_b": eval_b,
        "delta_b_vs_a": {
            "runoff_change_3yr_mm": round(eval_b["cumulative_runoff_3yr_mm"] - eval_a["cumulative_runoff_3yr_mm"], 2),
            "soil_loss_change_3yr_t_ha": round(
                eval_b["cumulative_soil_loss_3yr_t_ha"] - eval_a["cumulative_soil_loss_3yr_t_ha"], 3
            ),
            "soil_saved_by_b_tons": saved_soil_tons,
            "runoff_saved_by_b_mm": saved_runoff_mm,
            "cover_gain_pct": round(eval_b["mean_cover_pct_3yr"] - eval_a["mean_cover_pct_3yr"], 1),
        },
    }
