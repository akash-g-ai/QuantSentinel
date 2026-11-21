const About: React.FC = () => {
  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white">About QuantSentinel</h2>
        <p className="text-slate-400 mt-1">Financial Market Data Quality Validation Framework</p>
      </div>

      {/* What is QuantSentinel */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 shadow-lg">
        <h3 className="text-lg font-semibold text-white mb-4">What is QuantSentinel?</h3>
        <p className="text-slate-300 leading-relaxed mb-4">
          QuantSentinel is a <strong className="text-blue-400">financial market data quality validation framework</strong>.
          It inspects uploaded CSV datasets of daily OHLCV market data and produces a structured,
          traceable quality report before the data is used in quantitative research.
        </p>
        <div className="mt-4 bg-blue-900/20 border border-blue-800 rounded-lg p-4">
          <p className="text-sm text-blue-200">
            <strong className="text-blue-400">QuantSentinel is not:</strong>
          </p>
          <ul className="list-disc ml-5 mt-2 space-y-1 text-sm text-blue-100">
            <li>A trading system or trading signal generator</li>
            <li>A price prediction model</li>
            <li>An automated decision engine</li>
          </ul>
          <p className="text-sm text-blue-200 mt-2">It is a <strong>data quality gate</strong> for researchers and analysts.</p>
        </div>
      </div>

      {/* Validation Architecture */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 shadow-lg">
        <h3 className="text-lg font-semibold text-white mb-4">Validation Architecture</h3>
        <p className="text-slate-300 mb-4">
          The pipeline runs five sequential stages. Each stage is independent and produces typed
          findings that are assembled into a final quality report.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div className="bg-slate-900 p-4 rounded-lg border border-slate-700">
            <div className="font-semibold text-white mb-2">1. Ingestion</div>
            <p className="text-sm text-slate-400">File format, encoding, parseability</p>
          </div>
          <div className="bg-slate-900 p-4 rounded-lg border border-slate-700">
            <div className="font-semibold text-white mb-2">2. Structural</div>
            <p className="text-sm text-slate-400">Required columns, missing values, duplicates, data types, trading-day gaps</p>
          </div>
          <div className="bg-slate-900 p-4 rounded-lg border border-slate-700">
            <div className="font-semibold text-white mb-2">3. Financial</div>
            <p className="text-sm text-slate-400">OHLC consistency, non-positive prices, volume validity, duplicate dates</p>
          </div>
          <div className="bg-slate-900 p-4 rounded-lg border border-slate-700">
            <div className="font-semibold text-white mb-2">4. Statistical</div>
            <p className="text-sm text-slate-400">Abnormal returns, volume spikes, return outliers (MAD method)</p>
          </div>
          <div className="bg-slate-900 p-4 rounded-lg border border-slate-700">
            <div className="font-semibold text-white mb-2">5. Quality</div>
            <p className="text-sm text-slate-400">Aggregates findings into overall score and verdict</p>
          </div>
        </div>
      </div>

      {/* Scoring Formula */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 shadow-lg">
        <h3 className="text-lg font-semibold text-white mb-4">Scoring Formula</h3>
        <p className="text-slate-300 mb-4">
          Each finding carries a penalty based on severity. The final score is calculated as:
        </p>
        <div className="bg-slate-900 p-4 rounded-lg border border-slate-700 font-mono text-sm">
          score = max(0, 100 − total_penalty)
        </div>
        <div className="mt-4 grid grid-cols-3 gap-4">
          <div className="bg-slate-900 p-3 rounded-lg border border-red-900/50">
            <div className="text-red-400 font-medium mb-1">FAIL</div>
            <div className="text-slate-400 text-sm">10 points penalty</div>
          </div>
          <div className="bg-slate-900 p-3 rounded-lg border border-amber-900/50">
            <div className="text-amber-400 font-medium mb-1">WARNING</div>
            <div className="text-slate-400 text-sm">3 points penalty</div>
          </div>
          <div className="bg-slate-900 p-3 rounded-lg border border-green-900/50">
            <div className="text-green-400 font-medium mb-1">PASS</div>
            <div className="text-slate-400 text-sm">0 points penalty</div>
          </div>
        </div>
      </div>

      {/* Data Integrity */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 shadow-lg">
        <h3 className="text-lg font-semibold text-white mb-4">Data Integrity Guarantees</h3>
        <ul className="space-y-3">
          {[
            'Uploaded source files are never modified',
            'Rows are never dropped, filled, or reordered during validation',
            'Validation operates on a read-only copy of the loaded DataFrame',
            'Findings report what was found; they never alter the underlying data',
          ].map((item, i) => (
            <li key={i} className="flex items-start space-x-3">
              <span className="text-green-400 mt-1">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </span>
              <span className="text-slate-300">{item}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Footer */}
      <div className="text-center text-slate-500 text-sm pt-8 pb-4">
        <p>QuantSentinel - Financial Market Data Quality Validation Framework</p>
        <p className="mt-2">Not a trading system. Not a price-prediction model.</p>
      </div>
    </div>
  );
};

export default About;
