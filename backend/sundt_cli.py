import os
import dotenv
from projects_agent import ProjectsAgent
from awards_agent import AwardsAgent
import time

# Load environment variables
dotenv.load_dotenv()

class SundtCLI:
    def __init__(self):
        print("Initializing Sundt RAG CLI...")
        print("Loading agents...")
        self.projects_agent = ProjectsAgent()
        self.awards_agent = AwardsAgent()
        print("Agents loaded successfully!")
    
    def run(self):
        """Run the interactive CLI"""
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
                    print("\nAvailable commands:")
                    print("  projects <query> - Search for information about Sundt projects")
                    print("  awards <query>   - Search for information about Sundt awards")
                    print("  help             - Show this help message")
                    print("  exit             - Exit the application")
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
    
    def _handle_projects_query(self, query):
        """Process a query for the Projects agent"""
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
            
            # List the projects found
            if result.get("projects"):
                print("\nProjects found:")
                for i, project in enumerate(result["projects"], 1):
                    print(f"  {i}. {project.get('title', 'Untitled')}")
        else:
            print(f"\nNo results found. Reason: {result.get('reason', 'Unknown')}")
            print(f"Response: {result['response']}")
    
    def _handle_awards_query(self, query):
        """Process a query for the Awards agent"""
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
            
            # List the awards found
            if result.get("awards"):
                print("\nAwards found:")
                for i, award in enumerate(result["awards"], 1):
                    title = award.get('title', 'Untitled')
                    org = f" ({award.get('organization', '')})" if 'organization' in award else ""
                    print(f"  {i}. {title}{org}")
        else:
            print(f"\nNo results found. Reason: {result.get('reason', 'Unknown')}")
            print(f"Response: {result['response']}")

if __name__ == "__main__":
    # Check if OpenAI API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY environment variable not set.")
        print("Please create a .env file with your OpenAI API key:")
        print("OPENAI_API_KEY=your_api_key_here")
        exit(1)
    
    # Start the CLI
    cli = SundtCLI()
    cli.run()