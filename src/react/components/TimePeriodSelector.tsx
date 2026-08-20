import React from 'react';

export type TimePeriod = 'year' | 'lastYear' | 'all';

interface TimePeriodSelectorProps {
    value: TimePeriod;
    onChange: (period: TimePeriod) => void;
}

const TimePeriodSelector: React.FC<TimePeriodSelectorProps> = ({ value, onChange }) => {
    const options: { value: TimePeriod; label: string }[] = [
        { value: 'year', label: 'This Year' },
        { value: 'lastYear', label: 'Last Year' },
        { value: 'all', label: 'All Time' },
    ];

    return (
        <div className="time-period-selector">
            <span className="period-label">Time Period:</span>
            <div className="period-tabs">
                {options.map((option) => (
                    <button
                        key={option.value}
                        className={`period-tab ${value === option.value ? 'active' : ''}`}
                        onClick={() => onChange(option.value)}
                    >
                        {option.label}
                    </button>
                ))}
            </div>
        </div>
    );
};

export default TimePeriodSelector;