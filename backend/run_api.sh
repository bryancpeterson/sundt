#!/bin/bash
# Make sure you have installed all requirements
# pip install -r requirements.txt

# Make sure you have OpenAI API key in .env file
if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Creating template .env file."
    echo "OPENAI_API_KEY=your_api_key_here" > .env
    echo "Please edit the .env file and add your OpenAI API key."
    exit 1
fi

# Check if data directory exists
if [ ! -d "data" ]; then
    echo "WARNING: Data directory not found. Creating data directory."
    mkdir -p data
fi

# Check if crawlers have been run
if [ ! -f "data/projects.json" ] || [ ! -f "data/awards.json" ]; then
    echo "WARNING: Project or award data not found."
    echo "Would you like to run the crawlers now? (y/n)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        echo "Running projects crawler..."
        python -c "from crawlers.projects_crawler import SundtProjectsCrawler; SundtProjectsCrawler().crawl()"
        echo "Running awards crawler..."
        python -c "from crawlers.awards_crawler import SundtAwardsCrawler; SundtAwardsCrawler().crawl()"
    else
        echo "Skipping crawler execution. Some API endpoints may return empty results."
    fi
fi

# Run the API server
echo "Starting Sundt RAG API server..."
python api.py