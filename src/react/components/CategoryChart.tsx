import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../ui';

interface Subcategory {
    name: string;
    count: number;
}

interface CategoryDetail {
    label: string;
    count: number;
    subcategories: Subcategory[];
}

interface CategoryChartProps {
    categories: CategoryDetail[];
    maxCount: number;
    onCategoryClick?: (category: string) => void;
}

/* Subject colours are derived from the design tokens, so the treemap stays in
   the same palette as the rest of the app however many categories appear. Each
   tile carries its matching `on-` role as text: the token roles flip lightness
   between light and dark, so a hard-coded label colour would fail one theme. */
const CATEGORY_COLORS: { background: string; color: string }[] = [
    { background: 'var(--md-sys-color-primary)', color: 'var(--md-sys-color-on-primary)' },
    { background: 'var(--md-sys-color-secondary)', color: 'var(--md-sys-color-on-secondary)' },
    { background: 'var(--md-sys-color-tertiary)', color: 'var(--md-sys-color-on-tertiary)' },
    {
        background: 'color-mix(in srgb, var(--md-sys-color-primary) 55%, var(--md-sys-color-secondary))',
        color: 'var(--md-sys-color-on-primary)',
    },
    {
        background: 'color-mix(in srgb, var(--md-sys-color-secondary) 60%, var(--md-sys-color-tertiary))',
        color: 'var(--md-sys-color-on-secondary)',
    },
    {
        background: 'color-mix(in srgb, var(--md-sys-color-tertiary) 60%, var(--md-sys-color-primary))',
        color: 'var(--md-sys-color-on-tertiary)',
    },
    {
        background: 'color-mix(in srgb, var(--md-sys-color-primary) 60%, var(--md-sys-color-tertiary))',
        color: 'var(--md-sys-color-on-primary)',
    },
    {
        background: 'color-mix(in srgb, var(--md-sys-color-secondary) 55%, var(--md-sys-color-primary))',
        color: 'var(--md-sys-color-on-secondary)',
    },
];

const CategoryChart: React.FC<CategoryChartProps> = ({
    categories,
    maxCount,
    onCategoryClick,
}) => {
    const [expandedCategory, setExpandedCategory] = useState<string | null>(null);
    const [hoveredItem, setHoveredItem] = useState<string | null>(null);
    const navigate = useNavigate();

    if (!categories || categories.length === 0) {
        return <p className="no-data">No category data available.</p>;
    }

    const handleCategoryClick = (category: CategoryDetail, e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (expandedCategory === category.label) {
            setExpandedCategory(null);
        } else {
            setExpandedCategory(category.label);
        }
        if (onCategoryClick) {
            onCategoryClick(category.label);
        }
    };

    const handleSubcategoryClick = (categoryLabel: string, subcategoryName: string, e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        navigate(`/books?category=${encodeURIComponent(categoryLabel)}&subcategory=${encodeURIComponent(subcategoryName)}`);
    };

    const handleCategoryLinkClick = (categoryLabel: string, e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        navigate(`/books?category=${encodeURIComponent(categoryLabel)}`);
    };

    const getColor = (index: number): string => {
        return CATEGORY_COLORS[index % CATEGORY_COLORS.length].background;
    };

    const getTextColor = (index: number): string => {
        return CATEGORY_COLORS[index % CATEGORY_COLORS.length].color;
    };

    const totalBooks = categories.reduce((sum, c) => sum + c.count, 0);

    if (expandedCategory) {
        const category = categories.find(c => c.label === expandedCategory);
        if (category) {
            const maxSubCount = Math.max(...category.subcategories.map(s => s.count), 1);
            return (
                <div className="category-treemap">
                    <div className="category-breadcrumb">
                        <Button variant="text" onClick={() => setExpandedCategory(null)}>
                            ← Back to categories
                        </Button>
                        <span className="breadcrumb-title">{category.label}</span>
                        <span className="breadcrumb-count">{category.count} books</span>
                        <Button
                            variant="text"
                            onClick={(e) => handleCategoryLinkClick(category.label, e)}
                        >
                            View all →
                        </Button>
                    </div>
                    <div className="subcategory-grid">
                        {category.subcategories.map((sub, idx) => {
                            const percentage = (sub.count / maxSubCount) * 100;
                            const sharePercent = ((sub.count / totalBooks) * 100).toFixed(1);
                            return (
                                <a
                                    href={`/books?category=${encodeURIComponent(category.label)}&subcategory=${encodeURIComponent(sub.name)}`}
                                    key={sub.name}
                                    className={`subcategory-item ${hoveredItem === sub.name ? 'hovered' : ''}`}
                                    onClick={(e) => handleSubcategoryClick(category.label, sub.name, e)}
                                    onMouseEnter={() => setHoveredItem(sub.name)}
                                    onMouseLeave={() => setHoveredItem(null)}
                                >
                                    <div
                                        className="subcategory-bar"
                                        style={{
                                            height: `${percentage}%`,
                                            backgroundColor: getColor(idx),
                                        }}
                                    >
                                        <span className="subcategory-tooltip">
                                            {sub.count} books ({sharePercent}%)
                                        </span>
                                    </div>
                                    <span className="subcategory-label">{sub.name}</span>
                                    <span className="subcategory-count">{sub.count}</span>
                                </a>
                            );
                        })}
                    </div>
                </div>
            );
        }
    }

    // Main treemap view
    return (
        <div className="category-treemap">
            <div className="category-grid">
                {categories.map((category, idx) => {
                    const percentage = (category.count / maxCount) * 100;
                    const sharePercent = ((category.count / totalBooks) * 100).toFixed(1);
                    const hasSubcategories = category.subcategories && category.subcategories.length > 0;

                    return (
                        <div
                            key={category.label}
                            className={`category-item-interactive ${hoveredItem === category.label ? 'hovered' : ''} ${hasSubcategories ? 'expandable' : ''}`}
                            onClick={(e) => handleCategoryClick(category, e)}
                            onMouseEnter={() => setHoveredItem(category.label)}
                            onMouseLeave={() => setHoveredItem(null)}
                        >
                            <a
                                href={`/books?category=${encodeURIComponent(category.label)}`}
                                className="category-link"
                                onClick={(e) => handleCategoryLinkClick(category.label, e)}
                            >
                                <div
                                    className="category-block"
                                    style={{
                                        height: `${percentage}%`,
                                        backgroundColor: getColor(idx),
                                        color: getTextColor(idx),
                                    }}
                                >
                                    <div className="category-content">
                                        <span className="category-name">{category.label}</span>
                                        <span className="category-count">{category.count}</span>
                                        <span className="category-percent">{sharePercent}%</span>
                                        {hasSubcategories && (
                                            <span className="category-expand-hint">Click to expand</span>
                                        )}
                                    </div>
                                    <div className="category-tooltip">
                                        <strong>{category.label}</strong>
                                        <br />
                                        {category.count} books ({sharePercent}%)
                                        {hasSubcategories && (
                                            <>
                                                <br />
                                                <small>{category.subcategories.length} subcategories</small>
                                            </>
                                        )}
                                    </div>
                                </div>
                            </a>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

export default CategoryChart;