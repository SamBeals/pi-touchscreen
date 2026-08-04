import QtQuick
import QtQuick.Layouts

Item {
    id: root
    anchors.fill: parent

    // Background layers
    Rectangle {
        anchors.fill: parent
        color: Theme.background
        visible: Theme.backgroundType === "solid"
    }

    Rectangle {
        anchors.fill: parent
        visible: Theme.backgroundType === "gradient"
        gradient: Gradient {
            GradientStop { position: 0.0; color: Theme.backgroundStops.length > 0 ? Theme.backgroundStops[0] : Theme.background }
            GradientStop { position: 1.0; color: Theme.backgroundStops.length > 1 ? Theme.backgroundStops[1] : Theme.background }
        }
    }

    Image {
        anchors.fill: parent
        visible: Theme.backgroundType === "image" && Theme.backgroundImageUrl.length > 0
        source: Theme.backgroundImageUrl
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
    }

    // Dim overlay for readability over photo backgrounds
    Rectangle {
        anchors.fill: parent
        visible: Theme.backgroundType === "image"
        color: Theme.mode === "light" ? "#80FFFFFF" : "#99000000"
    }

    default property alias content: body.data

    Item {
        id: body
        anchors.fill: parent
        anchors.margins: Theme.pageMargin
    }
}
