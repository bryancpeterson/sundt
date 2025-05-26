import os
import dotenv
from projects_agent import ProjectsAgent
from awards_agent import AwardsAgent
import time

dotenv.load_dotenv()

class SundtCLI:
    def __init__(self):
        print("Initializing Sundt RAG CLI...")
        print("Loading agents...")
        self.projects_agent = ProjectsAgent()
        self.awards_agent = AwardsAgent()
        print("Agents loaded successfully!")
    
    def run(self):
        print("\n" + "="*60)
        print("               SUNDT CONSTRUCTION RAG SYSTEM")
        print("="*60)
        print("Welcome to the Sundt Construction RAG interface.")
        print("This system provides information about Sundt's projects and awards.")
        print("\nAvailable commands:")
        print("  projects <query> - Search for information about Sundt projects")
        print("  awards <query>   - Search for information about Sundt awards")
        print("  help             - Show this help message")
        print("  exit             - Exit the application")
        print("="*60)
        
        while True:
            try:
                user_input = input("\nEnter your command: ").strip()
                
                if not user_input:
                    continue
                    
                if user_input.lower() == "exit":
                    print("Thank you for using the Sundt RAG system. Goodbye!")
                    break
                    
                if user_input.lower() == "help":
                    self._show_help()
                    continue
                
                # Parse command and query
                parts = user_input.split(maxsplit=1)
                if len(parts) < 2:
                    print("Please provide a query after the command. Type 'help' for more information.")
                    continue
                    
                command, query = parts
                
                if command.lower() == "projects":
                    self._handle_projects_query(query)
                elif command.lower() == "awards":
                    self._handle_awards_query(query)
                else:
                    print(f"Unknown command: {command}")
                    print("Type 'help' to see available commands.")
            
            except KeyboardInterrupt:
                print("\nOperation cancelled by user.")
                break
            except Exception as e:
                print(f"Error: {str(e)}")
    
    def _show_help(self):
        print("\nAvailable commands:")
        print("  projects <query> - Search for information about Sundt projects")
        print("  awards <query>   - Search for information about Sundt awards")
        print("  help             - Show this help message")
        print("  exit             - Exit the application")
        print("\nExample queries:")
        print("  projects tell me about hospital projects in Arizona")
        print("  awards what safety awards has Sundt won?")
        print("  projects show me bridge construction work")
    
    def _handle_projects_query(self, query):
        print(f"\nSearching for projects related to: {query}")
        print("Processing...")
        
        start_time = time.time()
        result = self.projects_agent.run(query)
        duration = time.time() - start_time
        
        if result["success"]:
            print(f"\nFound {len(result.get('projects', []))} relevant projects")
            print(f"Response time: {duration:.2f} seconds")
            print("\nRESPONSE:")
            print(result["response"])
            
            # Show the projects that were found
            if result.get("projects"):
                print("\nProjects found:")
                for i, project in enumerate(result["projects"], 1):
                    title = project.get('title', 'Untitled')
                    location = f" ({project.get('location', 'Location unknown')})" if 'location' in project else ""
                    print(f"  {i}. {title}{location}")
        else:
            print(f"\nNo results found. Reason: {result.get('reason', 'Unknown')}")
            if result.get('reason') and 'injection' in result['reason'].lower():
                print("Your query appears to contain instructions that could interfere with normal operation.")
                print("Please try a straightforward question about Sundt projects.")
            else:
                print(f"Response: {result['response']}")
    
    def _handle_awards_query(self, query):
        print(f"\nSearching for awards related to: {query}")
        print("Processing...")
        
        start_time = time.time()
        result = self.awards_agent.run(query)
        duration = time.time() - start_time
        
        if result["success"]:
            print(f"\nFound {len(result.get('awards', []))} relevant awards")
            print(f"Response time: {duration:.2f} seconds")
            print("\nRESPONSE:")
            print(result["response"])
            
            # Show the awards that were found
            if result.get("awards"):
                print("\nAwards found:")
                for i, award in enumerate(result["awards"], 1):
                    title = award.get('title', 'Untitled')
                    org = f" ({award.get('organization', '')})" if 'organization' in award else ""
                    year = f" - {award.get('year', award.get('date', ''))}" if award.get('year') or award.get('date') else ""
                    print(f"  {i}. {title}{org}{year}")
        else:
            print(f"\nNo results found. Reason: {result.get('reason', 'Unknown')}")
            if result.get('reason') and 'injection' in result['reason'].lower():
                print("Your query appears to contain instructions that could interfere with normal operation.")
                print("Please try a straightforward question about Sundt awards.")
            else:
                print(f"Response: {result['response']}")

if __name__ == "__main__":
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY environment variable not set.")
        print("Please create a .env file with your OpenAI API key:")
        print("OPENAI_API_KEY=your_api_key_here")
        exit(1)
    
    # Start the CLI
    cli = SundtCLI()
    cli.run()