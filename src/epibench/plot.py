"""Start of the `plot` pipeline. Plot the models output data"""

from .config import Config

import logging
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
#import seaborn as sns
import warnings
warnings.filterwarnings('ignore')

from .benchmark_plotting import plot_components, plot_timeseries, plot_wis_heatmap, plot_cumulative_timeseries, plot_multi_location_stacked, print_ladderboard

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def plot(config_path=None):
    """
    Main execution function for the epibench `plot` pipeline.
    
    Args:
        config_path: path or directory where users save the score file to plot.
    """

    GROUP_COLORS = {'influpaint': 'green', 'flusight': 'blue'}
    
    group_map = {
    'JOSEPH': 'FluSight-baseline',
    'UNC_IDD-InfluPaint': 'influpaint',
    'UVAFluX-Ensemble': 'uvaflux'
    }
    
    # validate config
    logger.info("Validating config...")

    config_object = Config(
        config_path=config_path,
        pipeline="plot"
    )

    # Load score CSV
    logger.info("Loading CSV data...")

    score_df = pd.read_csv(config_object.score_file_path, dtype={'location': str})

    # Add column group
    score_df['group'] = score_df['model'].map(group_map).fillna('other')

    #print(config_object.score_file_path)
    #print(config_object.plot_output_dir)
    #print('df\n', score_df.head(2))

    #sys.exit() #breakpoint

    score_df['target_end_date'] = pd.to_datetime(score_df['target_end_date'])
    score_df['location'] = score_df['location'].astype(str).str.strip()

    # Add reference_date column to score_df
    # define the multiplier
    time_units_per_horizon = 7 # 7 days
    
    # Create reference_date
    score_df['reference_date'] = (score_df['target_end_date'] - pd.to_timedelta(score_df['horizon'] * time_units_per_horizon, unit='D'))
        
    # Filter out problematic models from analysis
    # i808 models have issues, UGuelph-CompositeCurve makes plot scale badly
    score_df = score_df[~score_df['model'].str.startswith('i808')]
    score_df = score_df[score_df['model'] != 'UGuelph-CompositeCurve']
    score_df = score_df[score_df['model'] != 'CADPH-FluCAT_Ensemble']
    
    # Calculate relative WIS against baseline for all data
    baseline_model = 'FluSight-baseline'
    if baseline_model in score_df['model'].unique():
        baseline_data = score_df[score_df['model'] == baseline_model].set_index(['location', 'target_end_date', 'horizon'])['wis']
        score_df['relative_wis'] = score_df.apply(
            lambda row: row['wis'] / baseline_data.get((row['location'], row['target_end_date'], row['horizon']), np.nan) 
            if baseline_data.get((row['location'], row['target_end_date'], row['horizon']), 0) > 0 else np.nan, 
            axis=1
        )
    else:
        score_df['relative_wis'] = np.nan

    print(f"\n{'='*50}")
    
    #############
    # WIS Heatmap
    #############
    # Plot wis heatmap with sum value over locations
    fig, ax = plot_wis_heatmap(
            df=score_df,
            location_filter="sum_all_states", 
            title=f"Absolute WIS Heatmap (Sum Over Locations)",
            relative=False, 
            original_df=None, 
            missing_info_fn=None, 
            group_colors=GROUP_COLORS,
            valid_locations=None
        )
    output_file = (config_object.plot_output_dir / "absolute_wis_heatmap_all_states.png")
    fig.savefig(output_file, dpi=200, bbox_inches='tight')
    plt.close(fig)

    # Plot relative wis heatmap with sum value over locations
    fig, ax = plot_wis_heatmap(
            df=score_df,
            location_filter="sum_all_states",
            title=f"Relative WIS Heatmap (Sum Over Locations)",
            relative=True,
            original_df=None,
            missing_info_fn=None,
            group_colors=GROUP_COLORS,
            valid_locations=None
        )
    output_file = (config_object.plot_output_dir / "relative_wis_heatmap_sum_all_states.png")
    fig.savefig(output_file, dpi=200, bbox_inches='tight')
    plt.close(fig)

    ########################
    # Full Performance Plot
    ########################
    # Sum over locations full performance plot
    
    allsum_data = score_df.copy() # simply use the original dataframe
    if not allsum_data.empty:
            plot_components(
                df=allsum_data,
                group_by=['model', 'group'],
                value_cols=['wis', 'dispersion', 'overprediction', 'underprediction', 
                           'interval_coverage_50', 'interval_coverage_90', 'relative_wis'],
                agg_func={'wis': 'sum', 'dispersion': 'sum', 'overprediction': 'sum', 'underprediction': 'sum',
                         'interval_coverage_50': 'mean', 'interval_coverage_90': 'mean', 'relative_wis': 'mean'},
                sort_by='wis',
                title=f"Full Performance (Sum Over Locations)",
                save_path= (config_object.plot_output_dir / "full_plot_sum_all_states.png"),
                missing_info=None,
                group_colors=GROUP_COLORS,
                reference_lines={
                    'interval_coverage_50': {'value': 0.5, 'label': 'Target 50%', 'color': 'red'},
                    'interval_coverage_90': {'value': 0.9, 'label': 'Target 90%', 'color': 'red'},
                    'relative_wis': {'value': 1.0, 'label': 'Baseline', 'color': 'black', 'linestyle': ':'}
                }
            )

    ################
    # Time Series
    ################
    # All States Time Series (Absolute WIS)
    all_states_data = score_df.copy()
    if not all_states_data.empty:
            plot_timeseries(
                df=all_states_data,
                x_col='target_end_date',
                y_col='wis',
                group_col='model',
                facet_col='horizon',
                filter_top_n=3,
                title=f"Absolute WIS Time Series (All States - Top 3 per Group)",
                save_path=(config_object.plot_output_dir / "absolute_timeseries_all_states.png"),
                relative=False
            )
            
            # Absolute WIS Cumulative Time Series
            # Filter to top 10 models per group for better readability
            if 'group' in all_states_data.columns:
                from .benchmark_plotting import get_top_models_per_group
                top_models = get_top_models_per_group(all_states_data, 'wis', top_n=10, relative=False)
                all_states_filtered = all_states_data[all_states_data['model'].isin(top_models)]
            else:
                # Fallback: top 10 overall
                model_avg = all_states_data.groupby('model')['wis'].mean().nsmallest(10)
                all_states_filtered = all_states_data[all_states_data['model'].isin(model_avg.index)]
            
            fig, ax = plot_cumulative_timeseries(
                plot_data=all_states_filtered,
                title=f"Cumulative WIS (All States - Top 10 per Group)",
                relative=False
            )
            output_file = (config_object.plot_output_dir / "cumulative_wis_all_states.png")
            fig.savefig(output_file, dpi=200, bbox_inches='tight')
            plt.close(fig)
            
            # Relative WIS Time Series
            plot_timeseries(
                df=all_states_data,
                x_col='target_end_date',
                y_col='relative_wis',
                group_col='model',
                facet_col='horizon',
                filter_top_n=3,
                title=f"Relative WIS Time Series (All States - Top 3 per Group)",
                save_path=(config_object.plot_output_dir / "relative_timeseries_all_states.png"),
                relative=True
            )
            
            # Relative WIS Cumulative Time Series
            # Filter to top 10 models per group for better readability
            if 'group' in all_states_data.columns:
                top_models_rel = get_top_models_per_group(all_states_data, 'relative_wis', top_n=10, relative=True)
                all_states_filtered_rel = all_states_data[all_states_data['model'].isin(top_models_rel)]
            else:
                # Fallback: top 10 overall (closest to 1.0 for relative)
                model_avg_rel = all_states_data.groupby('model')['relative_wis'].mean()
                closest_to_one = model_avg_rel.iloc[(model_avg_rel - 1.0).abs().argsort()[:10]]
                all_states_filtered_rel = all_states_data[all_states_data['model'].isin(closest_to_one.index)]
            
            fig, ax = plot_cumulative_timeseries(
                plot_data=all_states_filtered_rel,
                title=f"Relative Cumulative WIS (All States - Top 10 per Group)",
                relative=True
            )
            output_file = (config_object.plot_output_dir / "relative_cumulative_wis_all_states.png")
            fig.savefig(output_file, dpi=200, bbox_inches='tight')
            plt.close(fig)

    ###############################
    # States Stacked WIS Components
    ###############################    
    # Create states sum data
    states_sum = score_df.groupby(['model', 'group'], as_index=False).agg({
            'underprediction': 'sum', 'overprediction': 'sum', 'dispersion': 'sum'
        })
    states_sum['location'] = 'States_Sum'

    # Combine with original data
    states_plot_data = pd.concat([score_df, states_sum], ignore_index=True)

    all_locations = ['US', 'States_Sum'] + score_df['location'].unique().tolist()
    fig, axes = plot_multi_location_stacked(
            df=states_plot_data,
            locations=all_locations,
            reference_location='States_Sum',
            value_cols=['underprediction', 'overprediction', 'dispersion'],
            component_colors={'underprediction': 'red', 'overprediction': 'green', 'dispersion': 'blue'},
            title=f"WIS Components by State (Sorted by US Total WIS)",
            group_colors=GROUP_COLORS,
            location_name_mapper=None #$score_df['location']
        )
    output_file = (config_object.plot_output_dir / "wis_components_states_stacked.png")
    fig.savefig(output_file, dpi=200, bbox_inches='tight')
    plt.close(fig) 

    #####################################
    # Scatter Plots using plot_components
    #####################################
    # WIS vs Relative WIS scatter - All Locations
    plot_components(
            df=score_df,
            group_by=['model', 'group'],
            value_cols=['wis', 'relative_wis'], 
            agg_func={'wis': 'sum', 'relative_wis': 'mean'},
            title=f"WIS vs Relative WIS (All Locations)",
            save_path=(config_object.plot_output_dir / "wis_scatter_all_locations.png"),
            missing_info=None,
            group_colors=GROUP_COLORS,
            stacked=False,
            reference_lines={
                'relative_wis': {'value': 1.0, 'label': 'Baseline', 'color': 'black', 'linestyle': ':'}
            }
        )
    
    # Coverage scatter - All Locations
    plot_components(
            df=score_df,
            group_by=['model', 'group'],
            value_cols=['interval_coverage_50', 'interval_coverage_90'],
            agg_func={'interval_coverage_50': 'mean', 'interval_coverage_90': 'mean'},
            title=f"Coverage Comparison (All Locations)",
            save_path=(config_object.plot_output_dir / "coverage_scatter_all_locations.png"),
            missing_info=None,
            group_colors=GROUP_COLORS,
            stacked=False,
            reference_lines={
                'interval_coverage_50': {'value': 0.5, 'label': 'Target 50%', 'color': 'red'},
                'interval_coverage_90': {'value': 0.9, 'label': 'Target 90%', 'color': 'red'}
            }
        )

    logger.info(f"ALL PLOTS SAVED TO: {config_object.plot_output_dir}")

