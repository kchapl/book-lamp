import React from 'react';

interface GoalProgressProps {
    current: number;
    goal: number;
    year?: number;
}

const GoalProgress: React.FC<GoalProgressProps> = ({ current, goal, year = new Date().getFullYear() }) => {
    const percentage = goal > 0 ? Math.min((current / goal) * 100, 100) : 0;
    const remaining = Math.max(goal - current, 0);
    const isComplete = current >= goal;

    const radius = 45;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = circumference - (percentage / 100) * circumference;

    return (
        <div className="goal">
            <div className="goal-ring">
                <svg viewBox="0 0 100 100" width="104" height="104" aria-hidden="true">
                    <circle className="ring-bg" cx="50" cy="50" r={radius} strokeWidth="8" fill="none" />
                    <circle
                        className={`ring-fill ${isComplete ? 'is-complete' : ''}`}
                        cx="50"
                        cy="50"
                        r={radius}
                        strokeWidth="8"
                        fill="none"
                        strokeDasharray={circumference}
                        strokeDashoffset={strokeDashoffset}
                        strokeLinecap="round"
                    />
                </svg>
                <div className="goal-center">
                    <span className="goal-percent">{Math.round(percentage)}%</span>
                    {isComplete && <span className="goal-complete-icon">✓</span>}
                </div>
            </div>
            <div className="goal-details">
                <span className="goal-title">{year} reading goal</span>
                <span className="goal-stats">
                    <span className="goal-current numeric">{current}</span>
                    <span className="goal-separator">/</span>
                    <span className="goal-target numeric">{goal}</span>
                </span>
                {!isComplete && remaining > 0 && (
                    <span className="goal-remaining numeric">{remaining} more to reach your goal</span>
                )}
                {isComplete && <span className="goal-achieved">Goal reached</span>}
            </div>
        </div>
    );
};

export default GoalProgress;
