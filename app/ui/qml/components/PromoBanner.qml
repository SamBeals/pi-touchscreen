import QtQuick

Item {
    id: root
    property string sourceUrl: Theme.bannerUrl
    visible: sourceUrl.length > 0
    height: visible ? Math.min(220, width * 0.35) : 0

    Image {
        anchors.fill: parent
        source: root.sourceUrl
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: true
    }

    Rectangle {
        anchors.fill: parent
        radius: Theme.cornerRadius
        color: "transparent"
        border.color: Theme.surface
        border.width: 0
        clip: true
    }
}
