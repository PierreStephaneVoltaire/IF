#!/usr/bin/env python
"""Test script for health module renderer."""
import sys
sys.path.insert(0, 'src')

from health.renderer import render_program_summary, render_session

# Test session
session = {
    'date': '2026-03-08',
    'day': 'Sunday',
    'completed': True,
    'session_rpe': 8,
    'body_weight_kg': 82.5,
    'exercises': [
        {'name': 'Squat', 'sets': 5, 'reps': 5, 'kg': 140, 'rpe': 8},
        {'name': 'Bench', 'sets': 4, 'reps': 6, 'kg': 100, 'rpe': 7}
    ],
    'session_notes': 'Good session, squats felt smooth'
}

print("=== Session ===")
print(render_session(session))
print()

# Test program
program = {
    'meta': {
        'comp_date': '2026-06-14',
        'program_start': '2026-03-01',
        'target_total_kg': 500,
        'weight_class_kg': 83
    },
    'phases': [
        {'name': 'Hypertrophy', 'start_week': 1, 'end_week': 4, 'intent': 'Build muscle mass'},
        {'name': 'Strength', 'start_week': 5, 'end_week': 8, 'intent': 'Increase force production'}
    ],
    'sessions': [
        {
            'date': '2026-03-09',
            'day': 'Monday',
            'completed': False,
            'exercises': [{'name': 'Squat', 'sets': 5, 'reps': 5, 'kg': 140, 'rpe': 8}]
        },
        {
            'date': '2026-03-11',
            'day': 'Wednesday',
            'completed': False,
            'exercises': [{'name': 'Deadlift', 'sets': 3, 'reps': 5, 'kg': 180, 'rpe': 8}]
        }
    ],
    'diet_notes': [{'date': '2026-03-01', 'notes': 'Maintenance calories, 2g/kg protein'}],
    'supplements': [
        {'name': 'Creatine', 'dose': '5g daily'},
        {'name': 'Protein', 'dose': '2g/kg body weight'}
    ]
}

print("=== Program Summary ===")
print(render_program_summary(program))
