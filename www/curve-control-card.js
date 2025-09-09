// Curve Control Temperature Schedule Card
// Custom card for Home Assistant to display temperature schedule with electricity prices

class CurveControlCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('You need to define an entity');
    }
    this.config = config;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this.shadowRoot.lastElementChild) {
      this.shadowRoot.innerHTML = `
        <style>
          .card {
            padding: 16px;
            background: var(--ha-card-background, var(--card-background-color, white));
            border-radius: var(--ha-card-border-radius, 4px);
            box-shadow: var(--ha-card-box-shadow, 0 2px 2px 0 rgba(0, 0, 0, 0.14));
          }
          .header {
            font-size: 1.2em;
            font-weight: 500;
            margin-bottom: 16px;
          }
          .toggle-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 16px;
            padding: 8px;
            background: var(--secondary-background-color);
            border-radius: 4px;
          }
          .toggle-label {
            font-weight: 500;
          }
          .status-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-bottom: 16px;
          }
          .status-item {
            padding: 8px;
            background: var(--secondary-background-color);
            border-radius: 4px;
            text-align: center;
          }
          .status-value {
            font-size: 1.4em;
            font-weight: bold;
            color: var(--primary-color);
          }
          .status-label {
            font-size: 0.9em;
            color: var(--secondary-text-color);
            margin-top: 4px;
          }
          .chart-container {
            position: relative;
            height: 300px;
            margin-top: 16px;
          }
          canvas {
            width: 100% !important;
            height: 100% !important;
          }
          .no-data {
            text-align: center;
            padding: 32px;
            color: var(--secondary-text-color);
          }
          ha-switch {
            --mdc-theme-secondary: var(--switch-checked-color);
          }
        </style>
        <ha-card class="card">
          <div class="header">Curve Control Energy Optimizer</div>
          <div class="toggle-row">
            <span class="toggle-label">Use Optimized Schedule</span>
            <ha-switch id="optimization-toggle"></ha-switch>
          </div>
          <div class="status-row">
            <div class="status-item">
              <div class="status-value" id="savings-value">--</div>
              <div class="status-label">Savings</div>
            </div>
            <div class="status-item">
              <div class="status-value" id="status-value">--</div>
              <div class="status-label">Status</div>
            </div>
          </div>
          <div class="chart-container">
            <canvas id="schedule-chart"></canvas>
            <div id="no-data" class="no-data" style="display:none;">
              No schedule data available. Optimization will run at midnight or when you update preferences.
            </div>
          </div>
        </ha-card>
      `;
    }

    this.updateCard();
  }

  updateCard() {
    if (!this._hass) return;

    const switchEntity = this._hass.states['switch.curve_control_use_optimized_temperatures'];
    const savingsEntity = this._hass.states['sensor.curve_control_savings'];
    const statusEntity = this._hass.states['sensor.curve_control_status'];
    const chartEntity = this._hass.states['sensor.curve_control_temperature_schedule_chart'];

    // Update toggle
    const toggle = this.shadowRoot.getElementById('optimization-toggle');
    if (toggle && switchEntity) {
      toggle.checked = switchEntity.state === 'on';
      toggle.addEventListener('click', () => {
        this._hass.callService('switch', switchEntity.state === 'on' ? 'turn_off' : 'turn_on', {
          entity_id: 'switch.curve_control_use_optimized_temperatures'
        });
      });
    }

    // Update savings
    const savingsValue = this.shadowRoot.getElementById('savings-value');
    if (savingsValue && savingsEntity) {
      savingsValue.textContent = `$${savingsEntity.state || '0'}`;
    }

    // Update status
    const statusValue = this.shadowRoot.getElementById('status-value');
    if (statusValue && statusEntity) {
      statusValue.textContent = statusEntity.state || 'Unknown';
      statusValue.style.color = statusEntity.state === 'Optimized' ? '#4caf50' : 
                               statusEntity.state === 'Active' ? '#ff9800' : 
                               'var(--primary-color)';
    }

    // Update chart
    if (chartEntity && chartEntity.attributes.graph_data) {
      this.drawChart(chartEntity.attributes.graph_data);
      this.shadowRoot.getElementById('no-data').style.display = 'none';
      this.shadowRoot.getElementById('schedule-chart').style.display = 'block';
    } else {
      this.shadowRoot.getElementById('no-data').style.display = 'block';
      this.shadowRoot.getElementById('schedule-chart').style.display = 'none';
    }
  }

  drawChart(graphData) {
    const canvas = this.shadowRoot.getElementById('schedule-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!graphData || !graphData.datasets) return;

    const datasets = graphData.datasets;
    const labels = graphData.time_labels || [];
    
    // Simple chart drawing (basic implementation)
    const padding = 40;
    const chartWidth = canvas.width - padding * 2;
    const chartHeight = canvas.height - padding * 2;
    
    // Draw axes
    ctx.strokeStyle = '#ccc';
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, canvas.height - padding);
    ctx.lineTo(canvas.width - padding, canvas.height - padding);
    ctx.stroke();

    // Draw temperature line
    if (datasets[0] && datasets[0].data) {
      const temps = datasets[0].data;
      const minTemp = 65;
      const maxTemp = 80;
      
      ctx.strokeStyle = '#4caf50';
      ctx.lineWidth = 2;
      ctx.beginPath();
      
      temps.forEach((temp, i) => {
        const x = padding + (i / (temps.length - 1)) * chartWidth;
        const y = canvas.height - padding - ((temp - minTemp) / (maxTemp - minTemp)) * chartHeight;
        
        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });
      
      ctx.stroke();
    }

    // Draw price bars
    if (datasets[3] && datasets[3].data) {
      const prices = datasets[3].data;
      const maxPrice = 0.6;
      
      ctx.fillStyle = 'rgba(255, 152, 0, 0.3)';
      
      prices.forEach((price, i) => {
        const x = padding + (i / prices.length) * chartWidth;
        const barWidth = chartWidth / prices.length;
        const barHeight = (price / maxPrice) * chartHeight;
        const y = canvas.height - padding - barHeight;
        
        ctx.fillRect(x, y, barWidth, barHeight);
      });
    }

    // Draw labels
    ctx.fillStyle = '#666';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    
    // X-axis labels (every 3 hours)
    for (let i = 0; i < 24; i += 3) {
      const x = padding + (i / 24) * chartWidth;
      ctx.fillText(`${i}:00`, x, canvas.height - padding + 20);
    }
    
    // Y-axis labels
    ctx.textAlign = 'right';
    ctx.fillText('80°F', padding - 10, padding);
    ctx.fillText('72°F', padding - 10, padding + chartHeight / 2);
    ctx.fillText('65°F', padding - 10, canvas.height - padding);
  }

  getCardSize() {
    return 4;
  }
}

customElements.define('curve-control-card', CurveControlCard);

// Register the card with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'curve-control-card',
  name: 'Curve Control Card',
  description: 'Display temperature optimization schedule with controls'
});