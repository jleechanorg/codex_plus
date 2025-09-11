---
name: git-header
type: post-output
priority: 90
enabled: true
---
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class GitHeaderHook:
    """Post-output hook that displays git header after each response"""
    
    def __init__(self, name, config):
        self.name = name
        self.config = config
        self.priority = config.get('priority', 90)
        self.enabled = config.get('enabled', True)
        self.hook_type = config.get('type', 'post-output')
    
    async def post_output(self, response):
        """Execute git header script after API response"""
        try:
            # Find git root
            git_root = subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"], 
                text=True, 
                stderr=subprocess.DEVNULL
            ).strip()
            
            git_header_script = Path(git_root) / ".claude/hooks/git-header.sh"
            
            if git_header_script.exists() and git_header_script.is_file():
                # Execute the git header script
                result = subprocess.run(
                    [str(git_header_script)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.stdout.strip():
                    logger.info("🎯 Git Header:")
                    for line in result.stdout.strip().split('\n'):
                        logger.info(f"   {line}")
                    
                if result.stderr and result.returncode != 0:
                    logger.warning(f"Git header script warning: {result.stderr.strip()}")
                    
            else:
                logger.debug("Git header script not found or not executable")
                
        except subprocess.TimeoutExpired:
            logger.warning("Git header script timed out")
        except subprocess.CalledProcessError as e:
            logger.debug(f"Git header script failed: {e}")
        except Exception as e:
            logger.error(f"Error executing git header hook: {e}")
        
        return response