"""
Template Assistant Main Entry Point

Primary entry point for the Template Assistant application with support for both
interactive mode and quick launch mode via command-line arguments.

Usage:
    Interactive mode:
        python main.py
    
    Quick launch with template:
        python main.py --template example.template
    
    Quick launch with template and save file:
        python main.py --template example.template --save example.save

Quick launch mode automatically loads the specified files, renders the output,
then drops into interactive mode for further commands.
"""

import argparse
import sys
from interactive_shell import InteractiveShell


def parse_arguments():
    """
    Parse command-line arguments for quick launch mode.
    
    Returns:
        argparse.Namespace: Parsed arguments with template and save attributes
    """
    parser = argparse.ArgumentParser(
        description='Template Assistant - Interactive Jinja2 Template Rendering with Python Integration',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                                    # Interactive mode
  python main.py --template example.template        # Quick launch with template
  python main.py --template report.template \\       # Quick launch with both
                 --save client.save

Quick launch mode displays the banner, loads the specified files,
auto-renders the output, then drops into interactive mode.
        """
    )
    
    parser.add_argument(
        '--template', '-t',
        type=str,
        help='Path to template file for quick launch mode'
    )
    
    parser.add_argument(
        '--save', '-s',
        type=str,
        help='Path to save file for quick launch mode (optional)'
    )
    
    return parser.parse_args()


def main():
    """
    Main entry point for Template Assistant.
    
    Handles both interactive mode and quick launch mode based on
    command-line arguments.
    """
    try:
        # Parse command-line arguments
        args = parse_arguments()
        
        # Create interactive shell instance
        shell = InteractiveShell()
        
        # Determine launch mode based on arguments
        if args.template:
            # Quick launch mode with template (and optionally save file)
            shell.quick_launch(args.template, args.save)
        else:
            # Normal interactive mode
            shell.start()
            
    except KeyboardInterrupt:
        print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == '__main__':
    main()