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

    // Calculate the circumference for the circular progress
    const radius = 45;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = circumference - (percentage / 100) * circumference;

    return (
        <div className="goal-progress">
            <div className="goal-circle">
                <svg viewBox="0 0 100 100" className="progress-ring">
                    <circle
                        className="progress-ring-bg"
                        cx="50"
                        cy="50"
                        r={radius}
                        strokeWidth="8"
                        fill="none"
                    />
                    <circle
                        className={`progress-ring-fill ${isComplete ? 'complete' : ''}`}
                        cx="50"
                        cy="50"
                        r={radius}
                        strokeWidth="8"
                        fill="none"
                        strokeDasharray={circumference}
                        strokeDashoffset={strokeDashoffset}
                        strokeLinecap="round"
                        transform="rotate(-90 50 50)"
                    />
                </svg>
                <div className="goal-center">
                    <span className="goal-percent">{Math.round(percentage)}%</span>
                    {isComplete && <span className="goal-complete-icon">✓</span>}
                </div>
            </div>
            <div className="goal-details">
                <div className="goal-title">
                    {year} Reading Goal
                </div>
                <div className="goal-stats">
                    <span className="goal-current">{current}</span>
                    <span className="goal-separator">/</span>
                    <span className="goal-target">{goal}</span>
                </div>
                {!isComplete && remaining > 0 && (
                    <div className="goal-remaining">
                        {remaining} more to reach your goal
                    </div>
                )}
                {isComplete && (
                    <div className="goal-achieved">
                        Goal achieved! 🎉
                    </div>
                )}
            </div>
        </div>
    );
};

export default GoalProgress;